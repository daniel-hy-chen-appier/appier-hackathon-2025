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
<@{bot_user_id}> hangout-party <group_size> <party_discription> [--private=*true*|false]
"""



def analyze_user(target:str, event_data:dict):
    event_data['say'](f'loading data... please wait', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    # data.download_folder(os.environ["DATA_FOLDER_ID"], local_path='./data/')
    event_data['say'](f'done! analyzing...', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    with open("./data/personas/2024_happy_hour.json", 'rb') as f:
        content_2024 = f.read()
    with open("./data/personas/2025_happy_hour.json", 'rb') as f:
        content_2025 = f.read()
    
    response = gpt_response("gpt-4-turbo", [{"role":"user",
                                                    "content":[
                                                        {"type":"text",
                                                         "text":f"""give me the information for member {target} and tell me how to talk to he/her for first time, 
                                                         here is some data about all people
                                                         intro of 2024 newcomer
                                                         {content_2024}
                                                         intro of 2025 newcomer
                                                         {content_2025}
                                                         """},
                                                        ]
                                                    }])

    # shutil.rmtree('./data')
    return f"test for {target}, response:{response}"

def recommendation_user(group_size:int, party_discription:str, event_data:dict):
    event_data['say'](f'loading data... please wait', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    data.download_folder(os.environ["DATA_FOLDER_ID"], local_path='./data/')
    event_data['say'](f'done! analyzing...', thread_ts=event_data['thread_ts'], mrkdwn=True, ephemeral_user=event_data['user'])
    
    
    
    shutil.rmtree('./data')
    return []
    
@app.event("app_mention")
def handle_app_mention(event: dict, say: Say, client: slack_sdk.web.client.WebClient=None) -> None:
    bot_user_id = app.client.auth_test()["user_id"]
    # parse command
    user = event["user"]
    text = event.get("text", "help")
    thread_ts = event.get("thread_ts") or event.get("ts")
    text_arr = text.split()
    text_arr.remove(f"<@{bot_user_id}>")
    # for idx, text in enumerate( text_arr):
    #     if "=" in text:
    #         key, value = text.split("=", 1)
    #         text_arr[idx] = {key:value}
    private = True
    if len(text_arr) == 0 or text_arr[0] == 'help': # show help
        reply_text = f"<@{user}> Here are the available commands:\n{help_message(bot_user_id)}"
    elif text_arr[0] == "analyze-user":
        opts, args = getopt.getopt(text_arr[1:], 'hp:', ['help', 'private='])
        help_msg = f'<@{user}> Here is the help for analyze-user:\n<@{bot_user_id}> analyze-user <target_user> [--private=*true*|false]'
        logging.info(f'opts:{opts}\nargs:{args}')
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
    elif text_arr[0] == "hangout-party":
        opts, args = getopt.getopt(text_arr[1:], 'hp:', ['help', 'private='])
        help_msg = f'<@{user}> Here is the help for analyze-user:\n<@{bot_user_id}> hangout-party <group_size> <party_discription> [--private=*true*|false]'
        if len(args) == 2:
            if not args[0].isdigit():
                reply_text = help_msg
            else:
                group_size = int(args[0])
                party_description = args[1]
                recondation = recommendation_user(group_size, party_description, {"say":say, "thread_ts":thread_ts, "user":user})
                reply_text = f"<@{user}> Creating a hangout party for {group_size} people: {party_description}\nreconndation these prople:\n{' '.join(recondation)}"
                
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
    logging.info(f'event: {event}')
    logging.info(f'input text: {text}')
    # Reply in thread
    if client:
        if private:
            client.chat_postEphemeral(
                channel=event["channel"],
                user=user,
                text=reply_text,
                thread_ts=thread_ts,
                mrkdwn=True
            )
        else:
            client.chat_postMessage(
                channel=event["channel"],
                text=reply_text,
                thread_ts=thread_ts,
                mrkdwn=True
            )
    else:
        if private:
            say(reply_text, thread_ts=thread_ts, mrkdwn=True, ephemeral_user=user)
        else:
            say(reply_text, thread_ts=thread_ts, mrkdwn=True)

# Start the bot
if __name__ == "__main__":
    # Use Socket Mode Handler
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()