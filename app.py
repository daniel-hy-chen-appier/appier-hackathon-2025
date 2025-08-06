import os
import logging
from datetime import datetime, timedelta
import uuid
from openai import OpenAI
import slack_sdk
from slack_bolt import App, Say
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import getopt
import random
import time
import shutil
import glob
load_dotenv()
retries = 4

def authorize_drive():
    gauth = GoogleAuth()
    gauth.DEFAULT_SETTINGS['client_config_file'] = "creds/client_secrets.json"

    gauth.LoadCredentialsFile("creds/creds.txt")
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
    # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("creds/creds.txt")
    
    return GoogleDrive(gauth)


class Drive_object(object):
    def __init__(self):
        self.drive = authorize_drive() 
    # will need create(new), download(exist), upload(exist)
    # create also need to return id

    def create_new_file(self, local_path, new_name, folder_id, return_id=False):
        count = 0
        file = self.drive.CreateFile({'title':new_name, 'parents':[{'id':folder_id}]})
        file.SetContentFile(local_path)
        while True:
            try:
                file.Upload()
                if return_id == True:
                    return file['id']
            except:                
                if count == retries:                    
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1

    def download_file(self, local_path, file_id):
        count = 0
        file = self.drive.CreateFile({'id':file_id})
        while True:
            try:
                file.GetContentFile(local_path)
                return
            except:
                if count == retries:                    
                    return
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1                
        
    
    def update_file(self, local_path, file_id):
        count = 0
        file = self.drive.CreateFile({'id': file_id})
        file.SetContentFile(local_path)
        while True:
            try:                
                file.Upload()
                return
            except:
                if count == retries:
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1
    def download_folder(self, folder_id, local_path = '.'):
        if not os.path.exists(local_path):
            os.makedirs(local_path)

        file_list = self.drive.ListFile(
            {'q': f"'{folder_id}' in parents and trashed=false"}
        ).GetList()

        for file1 in sorted(file_list, key=lambda x: x['title']):
            title = file1['title']
            file_id = file1['id']
            mime_type = file1['mimeType']
            target_path = os.path.join(local_path, title)

            if mime_type == 'application/vnd.google-apps.folder':
                self.download_folder(file_id, target_path)
            else:
                print(f"Downloading file: {title} to {target_path}")
                self.download_file(target_path, file_id)
# Set up logging
logging.basicConfig(level=logging.INFO)
data = Drive_object()
# Initialize Slack Bolt App
# Make sure you have set environment variables SLACK_BOT_TOKEN and SLACK_APP_TOKEN
app = App(token=os.environ["SLACK_BOT_TOKEN"])
api_key = os.environ["API_KEY"]
gpt_client = OpenAI(api_key = api_key)
def gpt_loadfile(filepath:str):
    file = gpt_client.files.create(
        file=open(filepath, "rb"),
        purpose='assistants'
    )
    return file.id

def gpt_response(model:str, messages:str):
    completion = gpt_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
    )
    return completion.choices[0].message.content
def help_message(bot_user_id):
    return f"""
<@{bot_user_id}> help
<@{bot_user_id}> analyze-user <target_user> [--private=*true*|false]
<@{bot_user_id}> hangout-activity
"""



def analyze_user(target:str, event_data:dict):
    event_data['say'](f'loading data... please wait', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    data.download_folder(os.environ["DATA_FOLDER_ID"], local_path='./data/')
    event_data['say'](f'analyzing...', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    # with open("./data/personas/2024_happy_hour.json", 'rb') as f:
    #     content_2024 = f.read()
    # with open("./data/personas/2025_happy_hour.json", 'rb') as f:
    #     content_2025 = f.read()
    personas_dir = "./data/personas/"
    all_personas_content = []

    # Find all file paths in the directory ending with .json
    json_files = glob.glob(os.path.join(personas_dir, '*.json'))

    # Loop through each found file path
    for file_path in json_files:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Add the content to our list, using the filename for context
                content = f"--- Data from {filename} ---\n{f.read()}"
                all_personas_content.append(content)
        except IOError as e:
            print(f"Could not read file {file_path}: {e}")
    full_content_str = "\n\n".join(all_personas_content)
    mrkdwn_rule = """
Here are the mrkdwn syntax rules to follow:
Bold: *text*
Italic: _text_
Strikethrough: ~text~
Inline code: `code`
Code block: ```code block```
Blockquote: >quote
Links: <url|Link Text>
User Mentions: <@userid>
Channel Links: <#channelid>
& should be sent as &amp;
< should be sent as &lt;
> should be sent as &gt;
"""
    prompt = f"""
tell me waht kind of person {target} is?
show me his/her information like
job role, team, habit, intrest, skill,  persona tags, people she coordinates with most frequently

response me with mrkdwn format

here is some data about all person
{full_content_str}

mrkdwn rule:
{mrkdwn_rule}
    """
    
    response = gpt_response("gpt-4-turbo", [{"role":"user",
                                                    "content":[
                                                        {"type":"text",
                                                         "text":prompt},
                                                        ]
                                                    }])

    # shutil.rmtree('./data')
    return f"{response}"

def recommendation_user(group_size:int, activity_discription:str, event_data:dict):
    event_data['say'](
        channel=event_data['channel_id'], 
        user=event_data['user'],
        text=f'loading data... please wait')
    data.download_folder(os.environ["DATA_FOLDER_ID"], local_path='./data/')
    event_data['say'](channel=event_data['channel_id'], 
        user=event_data['user'],
        text=f'done! analyzing...')
    
    personas_dir = "./data/personas/"
    all_personas_content = []

    # Find all file paths in the directory ending with .json
    json_files = glob.glob(os.path.join(personas_dir, '*.json'))

    # Loop through each found file path
    for file_path in json_files:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Add the content to our list, using the filename for context
                content = f"--- Data from {filename} ---\n{f.read()}"
                all_personas_content.append(content)
        except IOError as e:
            print(f"Could not read file {file_path}: {e}")
    full_content_str = "\n\n".join(all_personas_content)
    mrkdwn_rule = """
Here are the mrkdwn syntax rules to follow:
Bold: *text*
Italic: _text_
Strikethrough: ~text~
Inline code: `code`
Code block: ```code block```
Blockquote: >quote
Links: <url|Link Text>
User Mentions: <@userid>
Channel Links: <#channelid>
& should be sent as &amp;
< should be sent as &lt;
> should be sent as &gt;
"""
    prompt = f"""
recommendate atmost {group_size} members to join a activity, 
you only need to list their name and give them a short reason, I will embed your response to a activity notice, so don't reply anything else 

here is the activaty's detail:
{activity_discription}

here is some data about all people:
{full_content_str}

mrkdwn rule:
{mrkdwn_rule}
    """
    
    response = gpt_response("gpt-4-turbo", [{"role":"user",
                                                    "content":[
                                                        {"type":"text",
                                                         "text":prompt},
                                                        ]
                                                    }])
    # shutil.rmtree('./data')
    return response

@app.view("hangout_activity_modal")
def handle_modal_submission(ack, body, client, view, logger):
    ack() 

    user = body["user"]["id"]
    values = view["state"]["values"]
    
    group_size = values["group_size_block"]["group_size_input"]["value"]
    activity_description = values["description_block"]["description_input"]["value"]
    channel_id = view["private_metadata"]

    if not group_size.isdigit():
        client.chat_postEphemeral(
            channel=channel_id, 
            user=user,
            text="❌ Group size must be a number.",
        )
        return

    group_size = int(group_size)

    recommendation = recommendation_user(group_size, activity_description, {"user": user, "say": client.chat_postMessage, "channel_id":channel_id})

    client.chat_postMessage(
        channel=channel_id, 
        text=f"<@{user}> 🎉 Here's a activity plan for {group_size} people:\n*{activity_description}*\nRecommended members:\n{recommendation}"
    )
@app.action("open_activity_modal")
def open_activity_modal(ack, body, client):
    ack()
    trigger_id = body.get("trigger_id")
    channel_id = body["channel"]["id"]

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "hangout_activity_modal",
            "private_metadata": channel_id,
            "title": {"type": "plain_text", "text": "Create Hangout activity"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "group_size_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "group_size_input"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Group Size"
                    }
                },
                {
                    "type": "input",
                    "block_id": "description_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "description_input",
                        "multiline": True
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "activity Description"
                    }
                }
            ]
        }
    )

@app.event("app_mention")
def handle_app_mention(event: dict, say: Say, client: slack_sdk.web.client.WebClient) -> None:
    bot_user_id = app.client.auth_test()["user_id"]
    # parse command
    user = event["user"]
    text = event.get("text", "help")
    thread_ts = event.get("thread_ts") or event.get("ts")
    text_arr = text.split()
    text_arr.remove(f"<@{bot_user_id}>")
    private = True
    if len(text_arr) == 0 or text_arr[0] == 'help': # show help
        private = False
        reply_text = f"<@{user}> Here are the available commands:\n{help_message(bot_user_id)}"
    elif text_arr[0] == "analyze-user":
        opts, args = getopt.getopt(text_arr[1:], 'hp:', ['help', 'private='])
        help_msg = f'<@{user}> Here is the help for analyze-user:\n<@{bot_user_id}> analyze-user <target_user> [--private=*true*|false]'
        if args:
            reply_text = analyze_user(args[0], {"say":say, "thread_ts":thread_ts, "user":user})
        else:
            reply_text = help_msg
        for opt_name, opt_value in opts:
            if opt_name in ('-h', '--help'):
                reply_text = help_msg
            elif opt_name in ('-p', '--private'):
                if opt_value.lower() in ["t","true"]:
                    private = True
                elif opt_value.lower() in ["f","false"]:
                    private = False
                else:
                    reply_text = help_msg
    elif text_arr[0] == "hangout-activity":
        say(text='click button to create a activity',
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "click button to create a activity👇"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "create activity"},
                            "action_id": "open_activity_modal"
                        }
                    ]
                }
            ])
        return
    else:
        private = False
        reply_text = f"<@{user}> Here are the available commands:\n{help_message(bot_user_id)}"
    # Reply in thread
    if client:
        if private:
            client.chat_postEphemeral(
                channel=event["channel"],
                user=user,
                text="private reply",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": reply_text
                        }
                    }
                ],
                thread_ts=thread_ts,
                mrkdwn=True
            )
        else:
            client.chat_postMessage(
                channel=event["channel"],
                text="here is the reply",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": reply_text
                        }
                    }
                ],
                thread_ts=thread_ts,
                mrkdwn=True
            )
    else:
        if private:
            say("private reply",blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": reply_text
                        }
                    }
                ], thread_ts=thread_ts, mrkdwn=True, ephemeral_user=user)
        else:
            say("here is the reply:",blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": reply_text
                        }
                    }
                ], thread_ts=thread_ts, mrkdwn=True)

# Start the bot
if __name__ == "__main__":
    # Use Socket Mode Handler
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()