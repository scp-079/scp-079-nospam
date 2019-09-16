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
from copy import deepcopy
from typing import Union

from pyrogram import Client, Filters, Message, User

from .. import glovar
from .channel import get_content
from .etc import get_channel_link, get_filename, get_entity_text, get_forward_name, get_full_name, get_now
from .etc import get_links, get_stripped_link, get_text
from .file import delete_file, get_downloaded_path, save
from .group import get_description, get_group_sticker, get_pinned
from .ids import init_group_id
from .image import get_color, get_file_id, get_ocr, get_qrcode
from .telegram import get_chat_member, get_sticker_title, resolve_username

# Enable logging
logger = logging.getLogger(__name__)


def is_class_c(_, message: Message) -> bool:
    # Check if the message is Class C object
    try:
        if message.from_user:
            uid = message.from_user.id
            gid = message.chat.id
            if init_group_id(gid):
                if uid in glovar.admin_ids[gid] or uid in glovar.bot_ids or message.from_user.is_self:
                    return True
    except Exception as e:
        logger.warning(f"Is class c error: {e}", exc_info=True)

    return False


def is_class_d(_, message: Message) -> bool:
    # Check if the message is Class D object
    try:
        if message.from_user:
            uid = message.from_user.id
            if uid in glovar.bad_ids["users"]:
                return True

        if message.forward_from:
            fid = message.forward_from.id
            if fid in glovar.bad_ids["users"]:
                return True

        if message.forward_from_chat:
            cid = message.forward_from_chat.id
            if cid in glovar.bad_ids["channels"]:
                return True
    except Exception as e:
        logger.warning(f"Is class d error: {e}", exc_info=True)

    return False


def is_class_e(_, message: Message, test: bool = False) -> bool:
    # Check if the message is Class E object
    try:
        if message.from_user and not test:
            # All groups' admins
            uid = message.from_user.id
            admin_ids = deepcopy(glovar.admin_ids)
            for gid in admin_ids:
                if uid in admin_ids[gid]:
                    return True

        if message.forward_from_chat:
            cid = message.forward_from_chat.id
            if cid in glovar.except_ids["channels"]:
                return True

        content = get_content(message)
        if content:
            if (content in glovar.except_ids["long"]
                    or content in glovar.except_ids["temp"]):
                return True
    except Exception as e:
        logger.warning(f"Is class e error: {e}", exc_info=True)

    return False


def is_declared_message(_, message: Message) -> bool:
    # Check if the message is declared by other bots
    try:
        if message.chat:
            gid = message.chat.id
            mid = message.message_id
            return is_declared_message_id(gid, mid)
    except Exception as e:
        logger.warning(f"Is declared message error: {e}", exc_info=True)

    return False


def is_exchange_channel(_, message: Message) -> bool:
    # Check if the message is sent from the exchange channel
    try:
        if message.chat:
            cid = message.chat.id
            if glovar.should_hide:
                if cid == glovar.hide_channel_id:
                    return True
            elif cid == glovar.exchange_channel_id:
                return True
    except Exception as e:
        logger.warning(f"Is exchange channel error: {e}", exc_info=True)

    return False


def is_from_user(_, message: Message) -> bool:
    # Check if the message is sent from a user
    try:
        if message.from_user:
            return True
    except Exception as e:
        logger.warning(f"Is from user error: {e}", exc_info=True)

    return False


def is_hide_channel(_, message: Message) -> bool:
    # Check if the message is sent from the hide channel
    try:
        if message.chat:
            cid = message.chat.id
            if cid == glovar.hide_channel_id:
                return True
    except Exception as e:
        logger.warning(f"Is hide channel error: {e}", exc_info=True)

    return False


def is_new_group(_, message: Message) -> bool:
    # Check if the bot joined a new group
    try:
        if message.new_chat_members:
            new_users = message.new_chat_members
            if new_users:
                for user in new_users:
                    if user.is_self:
                        return True
        elif message.group_chat_created or message.supergroup_chat_created:
            return True
    except Exception as e:
        logger.warning(f"Is new group error: {e}", exc_info=True)

    return False


def is_test_group(_, message: Message) -> bool:
    # Check if the message is sent from the test group
    try:
        if message.chat:
            cid = message.chat.id
            if cid == glovar.test_group_id:
                return True
    except Exception as e:
        logger.warning(f"Is test group error: {e}", exc_info=True)

    return False


class_c = Filters.create(
    func=is_class_c,
    name="Class C"
)

class_d = Filters.create(
    func=is_class_d,
    name="Class D"
)

class_e = Filters.create(
    func=is_class_e,
    name="Class E"
)

declared_message = Filters.create(
    func=is_declared_message,
    name="Declared message"
)

exchange_channel = Filters.create(
    func=is_exchange_channel,
    name="Exchange Channel"
)

from_user = Filters.create(
    func=is_from_user,
    name="From User"
)

hide_channel = Filters.create(
    func=is_hide_channel,
    name="Hide Channel"
)

new_group = Filters.create(
    func=is_new_group,
    name="New Group"
)

test_group = Filters.create(
    func=is_test_group,
    name="Test Group"
)


def is_avatar_image(path: str) -> bool:
    # Check if the image is avatar image
    try:
        # Check QRCODE
        qrcode = get_qrcode(path)
        if qrcode:
            if is_ban_text(qrcode) or is_regex_text("ava", qrcode):
                return True

        # Check OCR
        ocr = get_ocr(path)
        if ocr:
            if is_ban_text(ocr) or is_regex_text("ava", ocr):
                return True
    except Exception as e:
        logger.warning(f"Is avatar image error: {e}", exc_info=True)

    return False


def is_bad_message(client: Client, message: Message, text: str = None, image_path: str = None) -> str:
    # Check if the message should be watched
    result = ""
    if image_path:
        need_delete = [image_path]
    else:
        need_delete = []

    try:
        gid = message.chat.id

        # Regular message
        if not (text or image_path):
            # Bypass
            message_text = get_text(message)
            description = get_description(client, gid)
            if description and message_text == description:
                return ""

            pinned_message = get_pinned(client, gid)
            pinned_text = get_text(pinned_message)
            if pinned_text and message_text == pinned_text:
                return ""

            group_sticker = get_group_sticker(client, gid)
            if message.sticker:
                sticker_name = message.sticker.set_name
                if sticker_name == group_sticker:
                    return ""
            else:
                sticker_name = ""

            # Check detected records

            # If the user is being punished
            if is_detected_user(message):
                return "delete"

            # Content
            content = get_content(message)
            wb_user = is_watch_user(message, "ban")
            score_user = is_high_score_user(message)
            wd_user = is_watch_user(message, "delete")
            if content:
                detection = glovar.contents.get(content, "")
                if detection == "ban":
                    return detection

                if (wb_user or score_user) and detection == "wb":
                    return detection

                if detection == "delete":
                    return detection

                if (wb_user or score_user or wd_user) and detection == "wd":
                    return detection

                if content in glovar.bad_ids["contents"]:
                    return "delete content record"

            # Url
            detected_url = is_detected_url(message)
            if detected_url == "ban":
                return detected_url

            if (wb_user or score_user) and detected_url == "wb":
                return detected_url

            if detected_url == "delete":
                return detected_url

            if (wb_user or score_user or wd_user) and detected_url == "wd":
                return detected_url

            # Start detect ban

            # Check the message's text
            if message_text:
                if is_ban_text(message_text):
                    return "ban"

            # Check the forward from name:
            forward_name = get_forward_name(message)
            if forward_name and forward_name not in glovar.except_ids["long"]:
                if forward_name in glovar.bad_ids["contents"]:
                    return "ban name record"

                if is_nm_text(forward_name):
                    return "ban name"

            # Check the user's name:
            name = get_full_name(message.from_user)
            if name and name not in glovar.except_ids["long"]:
                if forward_name in glovar.bad_ids["contents"]:
                    return "ban name record"

                if is_nm_text(name):
                    return "ban name"

            # Check the filename:
            file_name = get_filename(message)
            if file_name:
                if is_ban_text(file_name):
                    return "ban"

            # Check image
            qrcode = ""
            ocr = ""
            all_text = message_text
            file_id, big = get_file_id(message)
            image_path = get_downloaded_path(client, file_id)
            if is_declared_message(None, message):
                return ""
            elif image_path:
                need_delete.append(image_path)
                if big:
                    qrcode = get_qrcode(image_path)
                    if qrcode:
                        if is_ban_text(qrcode):
                            return "ban"

                    ocr = get_ocr(image_path)
                    if ocr:
                        if is_ban_text(ocr):
                            return "ban"

                        all_text += ocr
                        if is_ban_text(all_text):
                            return "ban"

                    # QRCODE == con
                    if qrcode:
                        if is_regex_text("ad", all_text):
                            return "ban"

            # Start detect watch ban

            if wb_user or score_user:
                # Check the message's text
                if message_text:
                    if is_wb_text(message_text):
                        return "wb"

                # Check channel restriction
                if is_restricted_channel(message):
                    return "wb"

                # Check the forward from name:
                if forward_name and forward_name not in glovar.except_ids["long"]:
                    if is_wb_text(forward_name):
                        return "wb name"

                # Check the document filename:
                if file_name:
                    if is_wb_text(file_name):
                        return "wb"

                # Check exe file
                if is_exe(message):
                    return "wb"

                # Check Telegram link
                if is_tgl(client, message):
                    return "wb"

                # Check image
                if qrcode:
                    return "wb"

                if ocr:
                    if is_wb_text(ocr):
                        return "wb"

                if all_text:
                    if is_wb_text(all_text):
                        return "wb"

            # Start detect delete

            # Check the message's text
            if message_text:
                if is_delete_text(message_text):
                    return "delete"

            # Check the document filename:
            if file_name:
                if is_delete_text(file_name):
                    return "delete"

            # Check image
            if qrcode:
                if is_regex_text("del", qrcode):
                    return "delete"

            if ocr:
                if is_regex_text("del", ocr):
                    return "delete"

            if all_text:
                if is_regex_text("del", all_text):
                    return "delete"

            # Check sticker
            if sticker_name:
                if sticker_name not in glovar.except_ids["long"]:
                    if is_regex_text("sti", sticker_name):
                        return "delete"

                sticker_title = get_sticker_title(client, sticker_name)
                if sticker_title not in glovar.except_ids["long"]:
                    if is_regex_text("sti", sticker_title):
                        return f"delete name {sticker_title}"

            # Start detect watch delete

            if wb_user or score_user or wd_user:
                # Some media type
                if (message.animation
                        or message.audio
                        or message.document
                        or message.game
                        or message.location
                        or message.venue
                        or message.via_bot
                        or message.video
                        or message.video_note):
                    return "wd"

                # Forwarded message
                if message.forward_from_chat:
                    return "wd"

                # Check the message's text
                if message_text:
                    if is_wd_text(message_text):
                        return "wd"

                # Check image
                if qrcode:
                    return "wd"

                if ocr:
                    if is_wd_text(ocr):
                        return "wd"

                if all_text:
                    if is_wd_text(all_text):
                        return "wd"

                if image_path:
                    color = get_color(image_path)
                    if color:
                        return "wd"

            # Start detect bad

            # Check the message's text
            if message_text:
                if is_regex_text("bad", message_text):
                    return "bad"
        # Preview message
        else:
            # Start detect ban

            # Check the text
            if text:
                if is_ban_text(text):
                    return "ban"

            # Check image
            qrcode = ""
            ocr = ""
            all_text = text
            if image_path:
                need_delete.append(image_path)
                qrcode = get_qrcode(image_path)
                if qrcode:
                    if is_ban_text(qrcode):
                        return "ban"

                ocr = get_ocr(image_path)
                if ocr:
                    if is_ban_text(ocr):
                        return "ban"

                    all_text += ocr
                    if is_ban_text(all_text):
                        return "ban"

            # Start detect watch ban

            if is_watch_user(message, "ban") or is_high_score_user(message):
                # Check the text
                if text:
                    if is_wb_text(text):
                        return "wb"

                # Check image
                if qrcode:
                    return "wb"

                if ocr:
                    if is_wb_text(ocr):
                        return "wb"

                if all_text:
                    if is_wb_text(all_text):
                        return "wb"

            # Start detect delete

            # Check the text
            if text:
                if is_delete_text(text):
                    return "delete"

            # Check image
            if qrcode:
                if is_regex_text("del", qrcode):
                    return "delete"

            if ocr:
                if is_regex_text("del", ocr):
                    return "delete"

            if all_text:
                if is_regex_text("del", all_text):
                    return "delete"

            # Start detect watch delete

            if is_watch_user(message, "ban") or is_high_score_user(message) or is_watch_user(message, "delete"):
                # Check the text
                if text:
                    if is_wd_text(text):
                        return "wd"

                # Check image
                if qrcode:
                    return "wd"

                if ocr:
                    if is_wd_text(ocr):
                        return "wd"

                if all_text:
                    if is_wd_text(all_text):
                        return "wd"

                color = get_color(image_path)
                if color:
                    return "wd"

            # Start detect bad

            # Check the text
            if text:
                if is_regex_text("bad", text):
                    return "bad"
    except Exception as e:
        logger.warning(f"Is watch message error: {e}", exc_info=True)
    finally:
        for file in need_delete:
            delete_file(file)

    return result


def is_ban_text(text: str) -> bool:
    # Check if the text is ban text
    try:
        if is_regex_text("ban", text):
            return True

        if is_regex_text("ad", text) and is_regex_text("con", text):
            return True
    except Exception as e:
        logger.warning(f"Is ban text error: {e}", exc_info=True)

    return False


def is_bio_text(text: str) -> bool:
    # Check if the text is bio text
    try:
        if is_regex_text("bio", text):
            return True

        if is_ban_text(text):
            return True
    except Exception as e:
        logger.warning(f"Is bio text error: {e}", exc_info=True)

    return False


def is_delete_text(text: str) -> bool:
    # Check if the text is delete text
    try:
        if is_regex_text("del", text):
            return True

        if is_regex_text("spc", text):
            return True

        if is_regex_text("spe", text):
            return True
    except Exception as e:
        logger.warning(f"Is delete text error: {e}", exc_info=True)

    return False


def is_declared_message_id(gid: int, mid: int) -> bool:
    # Check if the message's ID is declared by other bots
    try:
        if mid in glovar.declared_message_ids.get(gid, set()):
            return True
    except Exception as e:
        logger.warning(f"Is declared message id error: {e}", exc_info=True)

    return False


def is_detected_url(message: Message) -> str:
    # Check if the message include detected url, return detected type
    try:
        if is_class_c(None, message):
            return ""

        links = get_links(message)
        for link in links:
            detected_type = glovar.contents.get(link, "")
            if detected_type:
                return detected_type
    except Exception as e:
        logger.warning(f"Is detected url error: {e}", exc_info=True)

    return ""


def is_detected_user(message: Message) -> bool:
    # Check if the message is sent by a detected user
    try:
        if message.from_user:
            gid = message.chat.id
            uid = message.from_user.id
            return is_detected_user_id(gid, uid)
    except Exception as e:
        logger.warning(f"Is detected user error: {e}", exc_info=True)

    return False


def is_detected_user_id(gid: int, uid: int) -> bool:
    # Check if the user_id is detected in the group
    try:
        user = glovar.user_ids.get(uid, {})
        if user:
            status = user["detected"].get(gid, 0)
            now = get_now()
            if now - status < glovar.punish_time:
                return True
    except Exception as e:
        logger.warning(f"Is detected user id error: {e}", exc_info=True)

    return False


def is_exe(message: Message) -> bool:
    # Check if the message contain a exe
    try:
        extensions = ["apk", "bat", "cmd", "com", "exe", "msi", "pif", "scr", "vbs"]
        if message.document:
            if message.document.file_name:
                file_name = message.document.file_name
                for file_type in extensions:
                    if re.search(f"[.]{file_type}$", file_name, re.I):
                        return True

            if message.document.mime_type:
                mime_type = message.document.mime_type
                if "application/x-ms" in mime_type or "executable" in mime_type:
                    return True

        extensions.remove("com")
        links = get_links(message)
        for link in links:
            for file_type in extensions:
                if re.search(f"[.]{file_type}$", link, re.I):
                    return True
    except Exception as e:
        logger.warning(f"Is exe error: {e}", exc_info=True)

    return False


def is_high_score_user(message: Message) -> Union[bool, float]:
    # Check if the message is sent by a high score user
    try:
        if message.from_user:
            uid = message.from_user.id
            user = glovar.user_ids.get(uid, {})
            if user:
                score = sum(user["score"].values())
                if score >= 3.0:
                    return score
    except Exception as e:
        logger.warning(f"Is high score user error: {e}", exc_info=True)

    return False


def is_new_user(user: User) -> bool:
    # Check if the message is sent from a new joined member
    try:
        uid = user.id
        if glovar.user_ids.get(uid, {}):
            if glovar.user_ids[uid].get("join", {}):
                now = get_now()
                for gid in list(glovar.user_ids[uid]["join"]):
                    join = glovar.user_ids[uid]["join"].get(gid, 0)
                    if now - join < glovar.time_new:
                        return True
    except Exception as e:
        logger.warning(f"Is new user error: {e}", exc_info=True)

    return False


def is_nm_text(text: str) -> bool:
    # Check if the text is nm text
    try:
        if (is_regex_text("nm", text)
                or is_regex_text("ban", text)
                or (is_regex_text("ad", text) and is_regex_text("con", text))
                or is_regex_text("bio", text)):
            return True
    except Exception as e:
        logger.warning(f"Is nm text error: {e}", exc_info=True)

    return False


def is_restricted_channel(message: Message) -> bool:
    # Check if the message is forwarded form restricted channel
    try:
        if message.forward_from_chat:
            if message.forward_from_chat.restriction_reason:
                return True
    except Exception as e:
        logger.warning(f"Is restricted channel error: {e}", exc_info=True)

    return False


def is_regex_text(word_type: str, text: str, again: bool = False) -> bool:
    # Check if the text hit the regex rules
    result = False
    try:
        if text:
            if not again:
                text = re.sub(r"\s{2,}", " ", text)
            elif " " in text:
                text = re.sub(r"\s", "", text)
            else:
                return False
        else:
            return False

        for word in list(eval(f"glovar.{word_type}_words")):
            if re.search(word, text, re.I | re.S | re.M):
                result = True

            # Match, count and return
            if result:
                count = eval(f"glovar.{word_type}_words").get(word, 0)
                count += 1
                eval(f"glovar.{word_type}_words")[word] = count
                save(f"{word_type}_words")
                return result

        # Try again
        return is_regex_text(word_type, text, True)
    except Exception as e:
        logger.warning(f"Is regex text error: {e}", exc_info=True)

    return result


def is_tgl(client: Client, message: Message) -> bool:
    # Check if the message includes the Telegram link
    try:
        # Bypass prepare
        gid = message.chat.id
        description = get_description(client, gid)
        pinned_message = get_pinned(client, gid)
        pinned_text = get_text(pinned_message)

        # Check links
        bypass = get_stripped_link(get_channel_link(message))
        links = get_links(message)
        tg_links = list(filter(lambda l: is_regex_text("tgl", l), links))
        bypass_list = [link for link in tg_links if (f"{bypass}/" in f"{link}/"
                                                     or link in description
                                                     or link in pinned_text)]
        if len(bypass_list) != len(tg_links):
            return True

        # Check text
        text = get_text(message)
        for bypass in bypass_list:
            text = text.replace(bypass, "")

        if is_regex_text("tgl", text):
            return True

        # Check mentions
        entities = message.entities or message.caption_entities
        if entities:
            for en in entities:
                if en.type == "mention":
                    username = get_entity_text(message, en)[1:]
                    if message.chat.username and username == message.chat.username:
                        continue

                    if username in description:
                        continue

                    if username in pinned_text:
                        continue

                    peer_type, peer_id = resolve_username(client, username)
                    if peer_type == "channel" and peer_id not in glovar.except_ids["channels"]:
                        return True

                    if peer_type == "user":
                        member = get_chat_member(client, message.chat.id, peer_id)
                        if member is False:
                            return True

                        if member and member.status not in {"creator", "administrator", "member", "restricted"}:
                            return True
    except Exception as e:
        logger.warning(f"Is tgl error: {e}", exc_info=True)

    return False


def is_watch_user(message: Message, the_type: str) -> bool:
    # Check if the message is sent by a watch user
    try:
        if message.from_user:
            uid = message.from_user.id
            now = get_now()
            until = glovar.watch_ids[the_type].get(uid, 0)
            if now < until:
                return True
    except Exception as e:
        logger.warning(f"Is watch user error: {e}", exc_info=True)

    return False


def is_wb_text(text: str) -> bool:
    # Check if the text is wb text
    try:
        if (is_regex_text("wb", text)
                or is_regex_text("iml", text)
                or is_regex_text("ad", text)
                or is_regex_text("aff", text)
                or is_regex_text("spc", text)
                or is_regex_text("spe", text)):
            return True
    except Exception as e:
        logger.warning(f"Is wb text error: {e}", exc_info=True)

    return False


def is_wd_text(text: str) -> bool:
    # Check if the text is wd text
    try:
        if (is_regex_text("wd", text)
                or is_regex_text("con", text)
                or is_regex_text("sho", text)
                or is_regex_text("tgp", text)):
            return True
    except Exception as e:
        logger.warning(f"Is wd text error: {e}", exc_info=True)

    return False
