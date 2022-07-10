import os
import random
import uuid

from flask import Flask, request, send_file, render_template
from PIL import Image, ImageDraw, ImageFont
import tarantool
import Levenshtein
import cv2
from image_similarity_measures.quality_metrics import ssim

TMP_FILE_NAME = "static/tmp.jpg"
TMP2_FILE_NAME = "static/tmp2.jpg"
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
    create_image_with_text(data[1], data[2], data[3], TMP_FILE_NAME)
    return send_file(TMP_FILE_NAME)


@app.route('/clear', methods=['UPDATE'])
def do_clear():
    for row in db.select():
        db.delete(row[0])
    return str(len(db.select()))


@app.route('/', methods=['GET'])
def do_template_get():
    files = db.select()
    if (len(files) == 0):
        return ""
    create_image_with_text(files[random.randint(0, len(files) - 1)][1],
                           files[random.randint(0, len(files) - 1)][2],
                           files[random.randint(0, len(files) - 1)][3], TMP2_FILE_NAME)
    return render_template('login.html', user_image=TMP2_FILE_NAME)


def get_random_mem_phrase():
    return memes[random.randint(0, len(memes) - 1)]


def create_new_meme(up_text: str, low_text: str, picture: bytes) -> str:
    id = uuid.uuid1()
    db.insert((str(id), up_text, low_text, picture))
    return str(id)


def create_image_with_text(up_text: str, low_text: str, picture: bytes, target_file_name: str):
    with open(target_file_name, "wb") as file:
        file.write(picture)
    image = Image.open(target_file_name)
    add_text_to_image(up_text, image, 100)
    add_text_to_image(low_text, image, image.height - 100)
    image.save(target_file_name)


def add_text_to_image(text: str, image: Image, height: int):
    draw_text = ImageDraw.Draw(image)
    draw_text.text(
        ((image.width - draw_text.textsize(text, font)[0]) / 2, height),
        text,
        font=font,
    )


if __name__ == '__main__':
    app.run()
