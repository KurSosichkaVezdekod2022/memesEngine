import os
import random
import subprocess
import uuid

from flask import Flask, request, send_file, render_template
from PIL import Image, ImageDraw, ImageFont
import tarantool
import Levenshtein
import cv2
from image_similarity_measures.quality_metrics import ssim

PATTERNS = ["#0077FF", "#00EAFF", "#8024C0", "#BEB6AE", "#FF3985", "#17D685"] + \
           [f"static/skins/{str(i)}.png" for i in range(1, 13)]
TMP_FILE_NAME = "static/tmp.png"
TMP2_FILE_NAME = "static/tmp2.png"
PNG_FILE_NAME = "static/convert.png"
connection = tarantool.connect("localhost", 3301)
db = connection.space("db3")
app = Flask(__name__)
font = ImageFont.truetype("vksans.ttf", 48)
memes = []
with open("memes.txt", "r") as file:
    memes = file.readlines()


def magick(file_name: str):
    image = Image.open(file_name)
    points = ((5, 5), (image.width - 5, 5),
              (5, image.height - 5), (image.width - 5, image.height - 5))
    image.close()
    bashCommand = f"convert {file_name} -quality 100 {PNG_FILE_NAME}"
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    process.wait()
    pattern = PATTERNS[random.randint(0, len(PATTERNS) - 1)]
    for point in points:
        process = subprocess.Popen(["convert", PNG_FILE_NAME, "-fuzz", "8%", "-fill", pattern, "-draw",
                                    f'color {point[0]},{point[1]} floodfill', "-quality", "100", PNG_FILE_NAME],
                                   stdout=subprocess.PIPE)
        process.wait()
    bashCommand = f"convert {PNG_FILE_NAME} -quality 100 {file_name}"
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    process.wait()


@app.route('/set', methods=['POST'])
def do_set():
    up_text = request.args.get("up_text")
    low_text = request.args.get("low_text")
    pic = request.get_data()
    with open(TMP_FILE_NAME, "wb") as file:
        file.write(pic)
    magick(TMP_FILE_NAME)
    with open(TMP_FILE_NAME, "rb") as file:
        pic = file.read(2 ** 32)
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
    if len(files) == 0:
        return render_template("empty.html")
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
    add_text_to_image(up_text, image, 70)
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
