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
from typing import Optional, Union

from pyrogram import Client, Message, User

from .. import glovar
from .etc import crypt_str, get_now, thread
from .channel import ask_for_help, auto_report, declare_message, forward_evidence, send_debug, share_bad_user
from .channel import share_watch_user, update_score
from .file import save
from .group import delete_message
from .filters import is_class_d, is_declared_message, is_detected_user, is_high_score_user
from .ids import init_user_id
from .telegram import get_users, kick_chat_member

# Enable logging
logger = logging.getLogger(__name__)


def add_bad_user(client: Client, uid: int) -> bool:
    # Add a bad user, share it
    try:
        if uid not in glovar.bad_ids["users"]:
            glovar.bad_ids["users"].add(uid)
            save("bad_ids")
            share_bad_user(client, uid)

        return True
    except Exception as e:
        logger.warning(f"Add bad user error: {e}", exc_info=True)

    return False


def add_detected_user(gid: int, uid: int) -> bool:
    # Add or update a detected user's status
    try:
        init_user_id(uid)
        now = get_now()
        previous = glovar.user_ids[uid]["detected"].get(gid)
        glovar.user_ids[uid]["detected"][gid] = now

        return bool(previous)
    except Exception as e:
        logger.warning(f"Add detected user error: {e}", exc_info=True)

    return False


def add_watch_user(client: Client, the_type: str, uid: int) -> bool:
    # Add a watch ban user, share it
    try:
        now = get_now()
        until = now + glovar.time_ban
        glovar.watch_ids[the_type][uid] = until
        until = str(until)
        until = crypt_str("encrypt", until, glovar.key)
        share_watch_user(client, the_type, uid, until)
        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Add watch user error: {e}", exc_info=True)

    return False


def ban_user(client: Client, gid: int, uid: Union[int, str]) -> bool:
    # Ban a user
    try:
        thread(kick_chat_member, (client, gid, uid))

        return True
    except Exception as e:
        logger.warning(f"Ban user error: {e}", exc_info=True)

    return False


def get_user(client: Client, uid: int) -> Optional[User]:
    # Get a user
    result = None
    try:
        result = get_users(client, [uid])
    except Exception as e:
        logger.warning(f"Get user error: {e}", exc_info=True)

    return result


def terminate_user(client: Client, message: Message, the_type: str, bio: str = None) -> bool:
    # Delete user's message, or ban the user
    try:
        if is_class_d(None, message) or is_declared_message(None, message):
            return True

        gid = message.chat.id
        uid = message.from_user.id
        mid = message.message_id
        type_list = the_type.split()
        action_type = type_list[0]
        if len(type_list) == 2:
            rule = type_list[1]
        else:
            rule = None

        if action_type == "ban":
            log_action = "自动封禁"
            log_rule = "全局规则"
            debug_action = "自动封禁"
            if rule:
                if rule == "bio":
                    log_rule = "简介检查"
                    debug_action = "简介封禁"
                elif rule == "nm":
                    log_rule = "名称检查"
                    debug_action = "名称封禁"
                elif rule == "nm-record":
                    log_rule = "名称收录"
                    debug_action = "名称封禁"
                elif rule == "record":
                    log_rule = "消息收录"
                    debug_action = "收录封禁"

            result = forward_evidence(client, message, log_action, log_rule, bio)
            if result:
                add_bad_user(client, uid)
                ban_user(client, gid, uid)
                delete_message(client, gid, mid)
                declare_message(client, gid, mid)
                ask_for_help(client, "ban", gid, uid)
                send_debug(client, message.chat, debug_action, uid, mid, result)
        elif action_type == "wb":
            log_action = "自动封禁"
            log_rule = "敏感追踪"
            debug_action = "追踪封禁"
            score_user = is_high_score_user(message)
            if score_user:
                log_rule = "用户评分"
                debug_action = "评分封禁"

            if rule:
                if rule == "nm":
                    log_rule = "名称追踪"
                    debug_action = "名称封禁"
                    if score_user:
                        log_rule = "名称评分"

            result = forward_evidence(client, message, log_action, log_rule, bio)
            if result:
                add_bad_user(client, uid)
                ban_user(client, gid, uid)
                delete_message(client, gid, mid)
                declare_message(client, gid, mid)
                ask_for_help(client, "ban", gid, uid)
                send_debug(client, message.chat, debug_action, uid, mid, result)
        elif action_type == "delete":
            log_action = "自动删除"
            log_rule = "全局规则"
            debug_action = "自动删除"
            more = ""
            if rule:
                if rule == "record":
                    log_rule = "消息收录"
                    debug_action = "收录删除"
                elif "nm" in rule:
                    more = rule.split("-")[1]

            if is_detected_user(message) or uid in glovar.recorded_ids[gid]:
                delete_message(client, gid, mid)
                add_detected_user(gid, uid)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(client, message, log_action, log_rule, 0.0, more)
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid)
                    if not previous:
                        update_score(client, uid)

                    send_debug(client, message.chat, debug_action, uid, mid, result)
        elif action_type == "wd":
            log_action = "自动删除"
            log_rule = "敏感追踪"
            debug_action = "追踪删除"
            score_user = is_high_score_user(message)
            if score_user:
                log_rule = "用户评分"
                debug_action = "评分删除"

            if is_detected_user(message) or uid in glovar.recorded_ids[gid]:
                delete_message(client, gid, mid)
                add_detected_user(gid, uid)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(client, message, log_action, log_rule)
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid)
                    if not previous:
                        update_score(client, uid)

                    send_debug(client, message.chat, debug_action, uid, mid, result)
        elif action_type == "bad":
            gid = message.chat.id
            count = glovar.user_ids[uid]["bad"].get(gid, 0)
            count += 1
            glovar.user_ids[uid]["bad"][gid] = count
            update_score(client, uid)
            if gid in glovar.report_ids:
                auto_report(client, message)

        return True
    except Exception as e:
        logger.warning(f"Terminate user error: {e}", exc_info=True)

    return False
