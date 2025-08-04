import os
import logging
from datetime import datetime, timedelta
import uuid

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler

# 設定日誌
logging.basicConfig(level=logging.INFO)

# 初始化 Bolt App
# 確保你已經設定了環境變數 SLACK_BOT_TOKEN 和 SLACK_APP_TOKEN
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# 初始化排程器
scheduler = BackgroundScheduler(timezone="Asia/Taipei") # 建議設定時區
scheduler.start()

# 簡易記憶體資料庫
# 警告：此資料庫會在程式重啟時清空。正式環境請使用真實資料庫。
db = {
    "events": {},
    "users":{}
}

# --- 監聽斜線命令 /create-event ---
@app.command("/create-event")
def handle_create_event_command(ack, body, client):
    # 確認收到命令
    ack()
    # 打開一個 Modal 視窗讓使用者填寫資訊
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "event_modal_submission",
            "title": {"type": "plain_text", "text": "建立新活動"},
            "submit": {"type": "plain_text", "text": "建立"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "event_name_block",
                    "label": {"type": "plain_text", "text": "活動名稱"},
                    "element": {"type": "plain_text_input", "action_id": "event_name_input"}
                },
                {
                    "type": "input",
                    "block_id": "event_start_block",
                    "label": {"type": "plain_text", "text": "開始時間（YYYY-MM-DD HH:MM）"},
                    "element": {"type": "plain_text_input", "action_id": "event_start_input"}
                },
                {
                    "type": "input",
                    "block_id": "event_end_block",
                    "label": {"type": "plain_text", "text": "結束時間（YYYY-MM-DD HH:MM）"},
                    "element": {"type": "plain_text_input", "action_id": "event_end_input"}
                },
                {
                    "type": "input",
                    "block_id": "event_place_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "地點（可選）"},
                    "element": {"type": "plain_text_input", "action_id": "event_place_input"}
                },
                {
                    "type": "input",
                    "block_id": "event_tag_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "標籤（可選，逗號分隔）"},
                    "element": {"type": "plain_text_input", "action_id": "event_tag_input"}
                }
            ]
        }
    )

# --- 監聽 Modal 提交 ---
@app.view("event_modal_submission")
def handle_event_modal_submission(ack, body, client, view, logger):
    # 確認收到提交
    ack()

    user_id = body["user"]["id"]
    channel_id = body.get("channel_id") # 注意：從 command 來的 body 沒有 channel_id，需要從其他地方取得或讓使用者選擇

    # 從 view 中取得使用者輸入的值
    event_name = view["state"]["values"]["event_name_block"]["event_name_input"]["value"]
    start_time_str = view["state"]["values"]["event_start_block"]["event_start_input"]["value"]
    end_time_str = view["state"]["values"]["event_end_block"]["event_end_input"]["value"]
    place = view["state"]["values"]["event_place_block"]["plain_text_input"]["value"] if "event_place_block" in view["state"]["values"] and "plain_text_input" in view["state"]["values"]["event_place_block"] else "None"
    tags = view["state"]["values"]["event_tag_block"]["plain_text_input"]["value"] if "event_tag_block" in view["state"]["values"] and "plain_text_input" in view["state"]["values"]["event_tag_block"] else ""
    tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
    try:
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        logger.error("時間格式錯誤")
        return

    # 產生唯一的事件 ID
    event_id = str(uuid.uuid4())
    # end_time = datetime.now() + timedelta(minutes=duration_minutes)

    # 儲存事件資訊
    db["events"][event_id] = {
        "name": event_name,
        "creator": user_id,
        "place": place,
        "attendees": set(), # 使用 set 來避免重複加入
        "start_time": start_time,
        "end_time": end_time,
        "channel_id": view['private_metadata'] or 'C0xxxxxx', # 在這邊填入你希望發布的預設頻道ID
        "event_tag": tags_list
    }
    
    logger.info(f"建立新活動: {db['events'][event_id]}")
    
    # 在頻道中發布事件通知
    try:
        result = client.chat_postMessage(
            channel=db['events'][event_id]["channel_id"],
            text=f"新活動！由 <@{user_id}> 發起的「{event_name}」已經開始了！",
            blocks=[
            {
                "type": "section",
                "text": {
                "type": "mrkdwn",
                "text": (
                    f"🎉 *新活動通知* 🎉\n\n"
                    f"由 <@{user_id}> 發起的活動：\n*「{event_name}」*\n\n"
                    f"*時間：* {start_time_str} ~ {end_time_str}\n"
                    f"*地點：* {place if place != 'None' else '未提供'}\n\n"
                    f"*tags:* {', '.join(tags_list)}\n"
                    "點擊下方按鈕加入！"
                )
                }
            },
            {
                "type": "context",
                "elements": [
                {
                    "type": "mrkdwn",
                    "text": "目前參加者：無"
                }
                ]
            },
            {
                "type": "actions",
                "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 加入活動"},
                    "style": "primary",
                    "action_id": "join_event_action",
                    "value": event_id
                }
                ]
            }
            
            ]
        )
        # 儲存訊息的時間戳，以便後續更新
        db["events"][event_id]["message_ts"] = result['ts']
    except Exception as e:
        logger.error(f"發送訊息失敗: {e}")
        return

    # 設定排程任務，在事件結束時發送回饋請求
    # 也可以在活動開始時發送提醒
    scheduler.add_job(
        lambda: client.chat_postMessage(
            channel=db['events'][event_id]["channel_id"],
            text=f"活動「{event_name}」即將開始！"
        ),
        'date',
        run_date=start_time
    )
    # 活動結束時發送回饋請求
    scheduler.add_job(
        send_feedback_request,
        'date',
        run_date=end_time,
        args=[event_id, client, logger]
    )

# --- 監聽按鈕點擊 ---
@app.action("join_event_action")
def handle_join_event_action(ack, body, client, logger):
    ack()

    user_id = body["user"]["id"]
    event_id = body["actions"][0]["value"]
    event = db["events"].get(event_id)

    if not event:
        logger.warning("找不到對應的活動")
        return

    # 將使用者加入參加者名單
    event["attendees"].add(user_id)
    logger.info(f"使用者 {user_id} 加入活動 {event_id}")

    # 更新原始訊息，顯示最新的參加者名單
    attendees_text = ", ".join([f"<@{u}>" for u in event["attendees"]]) or "無"
    
    try:
        client.chat_update(
            channel=event["channel_id"],
            ts=event["message_ts"],
            blocks=[
                event["blocks"][0], # 沿用舊的 block
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"目前參加者：{attendees_text}"
                        }
                    ]
                },
                event["blocks"][2] # 沿用舊的 block
            ]
        )
    except Exception as e:
        logger.error(f"更新訊息失敗: {e}")

# --- 排程執行的函式 ---
def send_feedback_request(event_id, client, logger):
    event = db["events"].get(event_id)
    if not event:
        logger.warning(f"排程任務執行時，找不到活動 {event_id}")
        return

    logger.info(f"活動 {event['name']} 已結束，開始發送回饋請求給 {len(event['attendees'])} 位參加者。")
    
    # 對每個參加者發送私訊
    for user_id in event["attendees"]:
        try:
            client.chat_postMessage(
                channel=user_id, # 直接使用 user_id 即可發送 DM
                text=f"嗨！感謝您參加「{event['name']}」活動，可以跟我們分享您的回饋嗎？"
            )
        except Exception as e:
            logger.error(f"發送 DM 給 {user_id} 失敗: {e}")
            
    # （可選）在原頻道更新訊息，宣告活動結束
    client.chat_update(
        channel=event["channel_id"],
        ts=event["message_ts"],
        text=f"活動「{event['name']}」已圓滿結束！",
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *活動「{event['name']}」已圓滿結束！*\n感謝大家的參與！回饋請求已私訊給各位參加者。"
                }
            }
        ]
    )

# --- 監聽私訊回覆 ---
@app.message()
def handle_message_events(message, logger):
    # 這個監聽器會收到所有 Bot 參與的訊息
    # 判斷是否為私訊
    if message.get("channel_type") == "im":
        user_id = message["user"]
        text = message["text"]
        logger.info(f"收到來自 {user_id} 的私訊回饋: {text}")
        # 在這裡，你可以將回饋儲存到資料庫
        # db['feedback'][user_id] = text
        # 你也可以回覆一則感謝訊息
        # app.client.chat_postMessage(channel=user_id, text="感謝您的回饋！")


# --- 啟動 Bot ---
if __name__ == "__main__":
    # 使用 Socket Mode Handler
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()