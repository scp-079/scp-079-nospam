# SCP-079-NOSPAM - Block spam in groups
# Copyright (C) 2019 SCP-079 <https://scp-079.org>
#
# This file is part of SCP-079-NOSPAM.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import re

from PIL import Image, ImageEnhance
from pyrogram import Message
from pytesseract import image_to_string
from pyzbar.pyzbar import decode

from .. import glovar
from .etc import t2t

# Enable logging
logger = logging.getLogger(__name__)


def get_color(path: str) -> bool:
    # Get the picture's color, check if most of it is yellow
    try:
        if not path:
            return False

        image = Image.open(path).convert('YCbCr')
        w, h = image.size
        data = image.getdata()
        cnt = 0
        for i, ycbcr in enumerate(data):
            y, cb, cr = ycbcr
            if 86 <= cb <= 117 and 140 <= cr <= 168:
                cnt += 1

        if cnt > w * h * 0.3:
            return True
    except Exception as e:
        logger.warning(f"Get color error: {e}", exc_info=True)

    return False


def get_file_id(message: Message) -> (str, bool):
    # Get media message's image file id
    file_id = ""
    big = False
    try:
        if (message.photo
                or (message.sticker and not message.sticker.is_animated)
                or message.document
                or message.game):
            if message.photo:
                file_id = message.photo.file_id
            elif message.sticker:
                file_id = message.sticker.file_id
            elif message.document:
                if (message.document.mime_type
                        and "image" in message.document.mime_type
                        and "gif" not in message.document.mime_type
                        and message.document.file_size
                        and message.document.file_size < glovar.image_size):
                    file_id = message.document.file_id
            elif message.game:
                file_id = message.game.photo.file_id

        if file_id:
            big = True
        elif ((message.animation and message.animation.thumbs)
              or (message.audio and message.audio.thumbs)
              or (message.video and message.video.thumbs)
              or (message.video_note and message.video_note.thumbs)
              or (message.document and message.document.thumbs)):
            if message.animation:
                file_id = message.animation.thumbs[-1].file_id
            elif message.audio:
                file_id = message.audio.thumbs[-1].file_id
            elif message.video:
                file_id = message.video.thumbs[-1].file_id
            elif message.video_note:
                file_id = message.video_note.thumbs[-1].file_id
            elif message.document:
                file_id = message.document.thumbs[-1].file_id
    except Exception as e:
        logger.warning(f"Get image status error: {e}", exc_info=True)

    return file_id, big


def get_ocr(path: str, test: bool = False) -> str:
    result = ""
    try:
        if not path:
            return ""

        image = Image.open(path)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2)
        result = image_to_string(image, lang='chi_sim+chi_tra')
        if not result:
            image = image.convert('L')
            image = get_processed_image(image)
            result = image_to_string(image, lang='chi_sim+chi_tra')

        if result:
            if test:
                result = re.sub(r"\n{2,}", "\n", result)
            else:
                result = re.sub(r"\n", " ", result)

            result = re.sub(r"\s{2,}", " ", result)
            result = t2t(result, False)
    except Exception as e:
        logger.warning(f"Get OCR error: {e}", exc_info=True)

    return result


def get_processed_image(image: Image.Image) -> Image.Image:
    try:
        image.thumbnail((200, 200))
        s = 0
        total = 0
        for count, color in image.getcolors(image.size[0] * image.size[1]):
            s += count * color
            total += count

        aver = int(s / total)
        if aver < 110:
            image = image.point(lambda x: 0 if x > aver + 20 else 255)
        else:
            image = image.point(lambda x: 0 if x < aver - 20 else 255)
    except Exception as e:
        logger.warning('Get image error: %s', e)

    return image


def get_qrcode(path: str) -> str:
    # Get QR code
    result = ""
    try:
        if not path:
            return ""

        # Open
        image = Image.open(path)

        # Gray
        image = image.convert("L")

        # Contrast
        image = ImageEnhance.Contrast(image).enhance(4.0)

        # Thresholding
        image = image.point(lambda x: 0 if x < 150 else 255)

        # Decode
        decoded_list = decode(image)
        if decoded_list:
            for decoded in decoded_list:
                if decoded.type == "QRCODE":
                    result += f"{decoded.data}\n"

            if result:
                result = result[:-1]
                result = t2t(result, False)
    except Exception as e:
        logger.warning(f"Get qrcode error: {e}", exc_info=True)

    return result
