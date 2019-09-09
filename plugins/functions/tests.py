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

from pyrogram import Client, Message

from .. import glovar
from .channel import get_content
from .etc import code, get_int, get_text, italic, thread, user_mention
from .file import delete_file, get_downloaded_path
from .filters import is_class_e, is_detected_url, is_regex_text
from .image import get_file_id, get_ocr, get_qrcode
from .telegram import send_message

# Enable logging
logger = logging.getLogger(__name__)


def nospam_test(client: Client, message: Message) -> bool:
    # Test image porn score in the test group
    try:
        message_text = get_text(message)
        if re.search("^管理员：[0-9]", message_text):
            aid = get_int(message_text.split("\n\n")[0].split("：")[1])
        else:
            aid = message.from_user.id

        text = ""

        # Detected record
        content = get_content(message)
        detection = glovar.contents.get(content, "")
        if detection:
            text += f"检测记录：{code(glovar.names[detection.split()[0]])}\n"

        # Detected url
        detection = is_detected_url(message)
        if detection:
            text += f"检测链接：{code(glovar.names[detection.split()[0]])}\n"

        # Bad record
        if content in glovar.bad_ids["temp"]:
            text += f"已被收录：{code('True')}\n"

        # Image
        file_id, big = get_file_id(message)
        if big:
            image_path = get_downloaded_path(client, file_id)
            if image_path:
                # QR code
                qrcode = get_qrcode(image_path)
                if qrcode:
                    text += f"二维码：" + "-" * 24 + "\n\n"
                    text += code(qrcode) + "\n\n"
                    type_list = [glovar.regex[w] for w in glovar.regex if is_regex_text(w, qrcode)]
                    if type_list:
                        text += f"二维码检查：" + "-" * 24 + "\n\n"
                        text += "\t" * 4 + italic("，".join(type_list)) + "\n\n"

                # OCR
                ocr = get_ocr(image_path, True)
                if ocr:
                    text += f"OCR 结果：" + "-" * 24 + "\n\n"
                    text += code(ocr) + "\n\n"
                    type_list = [glovar.regex[w] for w in glovar.regex if is_regex_text(w, ocr)]
                    if type_list:
                        text += f"OCR 检查：" + "-" * 24 + "\n\n"
                        text += "\t" * 4 + italic("，".join(type_list)) + "\n\n"

                # All text
                if message_text:
                    all_text = message_text + ocr
                    type_list = [glovar.regex[w] for w in glovar.regex if is_regex_text(w, all_text)]
                    if type_list:
                        text += f"综合文字：" + "-" * 24 + "\n\n"
                        text += "\t" * 4 + italic("，".join(type_list)) + "\n\n"

                delete_file(image_path)

        if text:
            text += f"白名单：{code(is_class_e(None, message))}\n"
            text = f"管理员：{user_mention(aid)}\n\n" + text
            thread(send_message, (client, glovar.test_group_id, text, message.message_id))

        return True
    except Exception as e:
        logger.warning(f"Nospam test error: {e}", exc_info=True)

    return False
