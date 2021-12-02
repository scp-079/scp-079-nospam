# SCP-079-NOSPAM - Block spam in groups
# Copyright (C) 2019-2020 SCP-079 <https://scp-079.org>
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

from pyrogram import Client
from pyrogram.types import Message

from .. import glovar
from .channel import get_content
from .etc import code, get_int, get_md5sum, get_text, italic, lang, mention_id, thread
from .file import delete_file, get_downloaded_path
from .filters import is_class_e, is_detected_url, is_regex_text
from .image import get_file_id, get_ocr, get_qrcode
from .telegram import send_message

# Enable logging
logger = logging.getLogger(__name__)


def nospam_test(client: Client, message: Message) -> bool:
    # Test image porn score in the test group
    result = False

    try:
        origin_text = get_text(message)

        if re.search(f"^{lang('admin')}{lang('colon')}[0-9]", origin_text):
            aid = get_int(origin_text.split("\n\n")[0].split(lang('colon'))[1])
        else:
            aid = message.from_user.id

        text = ""
        message_text = get_text(message, True, True)

        # Detected record
        content = get_content(message)
        detection = glovar.contents.get(content, "")

        if detection:
            text += f"{lang('record_content')}{lang('colon')}{code(lang(detection.split()[0]))}\n"

        # Detected url
        detection = is_detected_url(message, True)

        if detection:
            text += f"{lang('record_link')}{lang('colon')}{code(lang(detection.split()[0]))}\n"

        # Bad record
        if content in glovar.bad_ids["contents"] or message_text in glovar.bad_ids["contents"]:
            text += f"{lang('record_bad')}{lang('colon')}{code('True')}\n"

        # Recorded contact
        for contact in glovar.bad_ids["contacts"]:
            if not re.search(contact, message_text, re.I):
                continue

            text += f"{lang('record_contact')}{lang('colon')}{code(contact)}\n"

        # Image
        file_id, big = get_file_id(message)
        image_path = big and get_downloaded_path(client, file_id)
        image_hash = image_path and get_md5sum("file", image_path)
        qrcode = image_path and get_qrcode(image_path)
        ocr = image_path and get_ocr(image_path, True)
        image_path and thread(delete_file, (image_path,))

        # OCR
        text = nospam_test_ocr(text, ocr, message_text)

        # QR code
        text = nospam_test_qrcode(text, qrcode)

        # Check white list
        whitelisted = (is_class_e(None, message, True)
                       or message_text in glovar.except_ids["long"]
                       or image_hash in glovar.except_ids["temp"])

        if not text and not whitelisted:
            return False

        text = text.replace("\n\n\n", "\n\n")
        text = f"{lang('white_listed')}{lang('colon')}{code(whitelisted)}\n" + text
        text = f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n\n" + text
        thread(send_message, (client, glovar.test_group_id, text, message.message_id))

        result = True
    except Exception as e:
        logger.warning(f"Nospam test error: {e}", exc_info=True)

    return result


def nospam_test_ocr(text: str, ocr: str, message_text: str) -> str:
    # NOSPAM OCR test
    result = text

    try:
        if not ocr:
            return result

        result += f"\n{lang('ocr_result')}{lang('colon')}" + "-" * 24 + "\n\n"
        result += code(ocr) + "\n\n"

        type_list = [lang(t) for t in glovar.regex if is_regex_text(t, ocr, True)]

        if type_list:
            result += f"{lang('ocr')}{lang('colon')}" + "-" * 24 + "\n\n"
            result += "\t" * 4 + italic(lang("comma").join(type_list)) + "\n\n"

        # All text
        if not message_text:
            return result

        all_text = message_text + ocr

        type_list = [lang(t) for t in glovar.regex if is_regex_text(t, all_text)]

        if not type_list:
            return result

        result += f"{lang('all_text')}{lang('colon')}" + "-" * 24 + "\n\n"
        result += "\t" * 4 + italic(lang("comma").join(type_list)) + "\n\n"
    except Exception as e:
        logger.warning(f"Nospam test ocr error: {e}", exc_info=True)

    return result


def nospam_test_qrcode(text: str, qrcode: str) -> str:
    # NOSPAM QRCODE test
    result = text

    try:
        if not qrcode:
            return result

        text += f"\n{lang('qrcode')}{lang('colon')}" + "-" * 24 + "\n\n"
        text += code(qrcode) + "\n\n"

        type_list = [lang(t) for t in glovar.regex if is_regex_text(t, qrcode)]

        if not type_list:
            return result

        text += f"{lang('qrcode_examine')}{lang('colon')}" + "-" * 20 + "\n\n"
        text += "\t" * 4 + italic(lang("comma").join(type_list)) + "\n\n"
    except Exception as e:
        logger.warning(f"Nospam test qrcode error: {e}", exc_info=True)

    return result
