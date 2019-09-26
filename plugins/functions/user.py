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
from .etc import get_now, thread
from .channel import ask_for_help, auto_report, declare_message, forward_evidence, send_debug, share_bad_user
from .channel import update_score
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
        if result:
            result = result[0]
    except Exception as e:
        logger.warning(f"Get user error: {e}", exc_info=True)

    return result


def terminate_user(client: Client, message: Message, user: User, context: str) -> bool:
    # Delete user's message, or ban the user
    try:
        if is_class_d(None, message) or is_declared_message(None, message):
            return True

        # Basic info
        gid = message.chat.id
        uid = user.id
        mid = message.message_id
        context_list = context.split()
        the_type = context_list[0]
        if len(context_list) >= 2:
            rule = context_list[1]
        else:
            rule = None

        if len(context_list) >= 3:
            more = " ".join(context_list[2:])
        else:
            more = None

        # Group config
        report_only = glovar.configs[gid].get("report", False)

        # Start process

        # Auto report to WARN
        if report_only or the_type == "bad":
            log_action = "自动评分"
            log_rule = "全局规则"
            debug_action = "微量评分"
            if rule == "name":
                log_rule = "名称检查"

            if uid in glovar.recorded_ids[gid] and is_high_score_user(message):
                return True

            result = forward_evidence(client, message, user, log_action, log_rule, 0.0, more)
            if result:
                if init_user_id(uid):
                    count = glovar.user_ids[uid]["bad"].get(gid, 0)
                    count += 1
                    glovar.user_ids[uid]["bad"][gid] = count
                    update_score(client, uid)
                    if gid in glovar.report_ids and uid not in glovar.recorded_ids[gid]:
                        auto_report(client, message)

                    glovar.recorded_ids[gid].add(uid)
                    send_debug(client, message.chat, debug_action, uid, mid, result)
        # Ban the user
        elif the_type == "ban":
            log_action = "自动封禁"
            log_rule = "全局规则"
            debug_action = "自动封禁"
            if rule != "bot":
                if rule == "bio":
                    log_rule = "简介检查"
                    debug_action = "简介封禁"
                elif rule == "name":
                    if more == "record":
                        log_rule = "名称收录"
                        debug_action = "名称封禁"
                    else:
                        log_rule = "名称检查"
                        debug_action = "名称封禁"
                elif rule == "record":
                    log_rule = "消息收录"
                    debug_action = "收录封禁"

                result = forward_evidence(client, message, user, log_action, log_rule, 0.0, more)
                if result:
                    declare_message(client, gid, mid)
                    ban_user(client, gid, user.username or user.id)
                    delete_message(client, gid, mid)
                    ask_for_help(client, "ban", gid, uid)
                    add_bad_user(client, uid)
                    send_debug(client, message.chat, debug_action, uid, mid, result)
            else:
                log_action = "自动封禁"
                log_rule = "群组自定义"
                debug_action = "阻止机器人"
                result = forward_evidence(client, message, user, log_action, log_rule, 0.0, more)
                if result:
                    ban_user(client, gid, user.username or user.id)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    ask_for_help(client, "delete", gid, uid)
                    send_debug(client, message.chat, debug_action, uid, mid, result)
        # Watch ban the user
        elif the_type == "wb":
            log_action = "自动封禁"
            log_rule = "敏感追踪"
            debug_action = "追踪封禁"
            score_user = is_high_score_user(message)
            if score_user:
                log_rule = "用户评分"
                debug_action = "评分封禁"

            if rule == "name":
                log_rule = "名称追踪"
                debug_action = "名称封禁"
                if score_user:
                    log_rule = "名称评分"

            result = forward_evidence(client, message, user, log_action, log_rule, score_user, more)
            if result:
                add_bad_user(client, uid)
                ban_user(client, gid, user.username or user.id)
                delete_message(client, gid, mid)
                declare_message(client, gid, mid)
                ask_for_help(client, "ban", gid, uid)
                send_debug(client, message.chat, debug_action, uid, mid, result)
        # Delete the message
        elif the_type in {"delete", "true"}:
            log_action = "自动删除"
            log_rule = "全局规则"
            debug_action = "自动删除"
            if rule == "record":
                log_rule = "消息收录"
                debug_action = "收录删除"

            if is_detected_user(message) or uid in glovar.recorded_ids[gid] or the_type == "true":
                delete_message(client, gid, mid)
                add_detected_user(gid, uid)
                declare_message(client, gid, mid)
            else:
                result = forward_evidence(client, message, user, log_action, log_rule, 0.0, more)
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid)
                    if not previous:
                        update_score(client, uid)

                    send_debug(client, message.chat, debug_action, uid, mid, result)
        # Watch delete the message
        elif the_type == "wd":
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
                result = forward_evidence(client, message, user, log_action, log_rule, score_user, more)
                if result:
                    glovar.recorded_ids[gid].add(uid)
                    delete_message(client, gid, mid)
                    declare_message(client, gid, mid)
                    previous = add_detected_user(gid, uid)
                    if not previous:
                        update_score(client, uid)

                    send_debug(client, message.chat, debug_action, uid, mid, result)

        return True
    except Exception as e:
        logger.warning(f"Terminate user error: {e}", exc_info=True)

    return False
