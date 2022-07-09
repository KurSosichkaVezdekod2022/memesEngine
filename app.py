import random
import uuid

from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
import tarantool
import Levenshtein
import cv2
from image_similarity_measures.quality_metrics import ssim

TMP_FILE_NAME = "tmp.jpg"
connection = tarantool.connect("localhost", 3301)
db = connection.space("db3")
app = Flask(__name__)
font = ImageFont.truetype("arial.ttf", 48)
memes = []
with open("memes.txt", "r") as file:
    memes = file.readlines()

@app.route('/set', methods=['POST'])
def do_set():
    up_text = request.args.get("up_text")
    low_text = request.args.get("low_text")
    pic = request.get_data()
    if up_text and low_text and len(pic) > 0:
        return create_new_meme(up_text, low_text, request.get_data())
    elif up_text and low_text:
        if len(db.select()) == 0:
            return "I haven't pictures"
        max_sim = -1
        max_sim_id = ""
        for row in db.select():
            sim = Levenshtein.jaro(up_text, row[1]) + Levenshtein.jaro(low_text, row[2])
            if sim > max_sim:
                max_sim = sim
                max_sim_id = row[0]
        return max_sim_id
    elif len(pic) > 0:
        if len(db.select()) == 0:
            return create_new_meme(get_random_mem_phrase(), get_random_mem_phrase(), pic)
        max_sim = -1
        max_sim_id = ""
        with open(TMP_FILE_NAME, "wb") as file:
            file.write(pic)
        picture = cv2.imread(TMP_FILE_NAME)
        dim = (picture.shape[1], picture.shape[0])
        for row in db.select():
            with open(TMP_FILE_NAME, "wb") as file:
                file.write(row[3])
            data_img = cv2.imread(TMP_FILE_NAME)
            resized_img = cv2.resize(data_img, dim, interpolation=cv2.INTER_AREA)
            sim = ssim(resized_img, picture)
            if sim > max_sim:
                max_sim = sim
                max_sim_id = row[0]
        src = db.select(max_sim_id)[0]
        if random.randint(0, 1) == 1:
            return create_new_meme(get_random_mem_phrase(), src[2], pic)
        else:
            return create_new_meme(src[1], get_random_mem_phrase(), pic)
    else:
        return "what?"



@app.route('/get', methods=['GET'])
def do_get():
    id = request.args.get("id")
    data = db.select(id)[0]
    with open(TMP_FILE_NAME, "wb") as file:
        file.write(data[3])
    image = Image.open(TMP_FILE_NAME)
    draw_text = ImageDraw.Draw(image)
    draw_text.text(
        ((image.width - draw_text.textsize(data[1], font)[0]) / 2, 100),
        data[1],
        font=font,
    )
    draw_text.text(
        ((image.width - draw_text.textsize(data[2], font)[0]) / 2, image.height - 100),
        data[2],
        font=font,
    )
    image.save(TMP_FILE_NAME)
    return send_file(TMP_FILE_NAME)


@app.route('/clear', methods=['UPDATE'])
def do_clear():
    for row in db.select():
        db.delete(row[0])
    return str(len(db.select()))


def get_random_mem_phrase():
    return memes[random.randint(0, len(memes) - 1)]

def create_new_meme(up_text: str, low_text: str, picture: bytes) -> str:
    id = uuid.uuid1()
    db.insert((str(id), up_text, low_text, picture))
    return str(id)


if __name__ == '__main__':
    app.run()
