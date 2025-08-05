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
load_dotenv()
# gauth = GoogleAuth()
# gauth.LoadCredentialsFile("creds.txt")
# if gauth.credentials is None:
#     # Authenticate if they're not there
#     gauth.LocalWebserverAuth()
# elif gauth.access_token_expired:
# # Refresh them if expired
#     gauth.Refresh()
# else:
#     # Initialize the saved creds
#     gauth.Authorize()
# # Save the current credentials to a file
# gauth.SaveCredentialsFile("creds.txt")

# def authorize_drive():
#     gauth = GoogleAuth()
#     gauth.DEFAULT_SETTINGS['client_config_file'] = "client_secrets.json"
#     gauth.LoadCredentialsFile("creds.txt")
#     return GoogleDrive(gauth)


# class Drive_object(object):
#     def __init__(self):
#         self.drive = authorize_drive() 

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Slack Bolt App
# Make sure you have set environment variables SLACK_BOT_TOKEN and SLACK_APP_TOKEN
app = App(token=os.environ["SLACK_BOT_TOKEN"])
api_key = os.environ["API_KEY"]
gpt_client = OpenAI(api_key = api_key)
def gpt_response(model:str, messages:str):
    completion = gpt_client.chat.completions.create(
        model=model,
        messages=messages
    )
    return completion.choices[0].message
def help_message(bot_user_id):
    return f"""
<@{bot_user_id}> help
<@{bot_user_id}> analyze-user <target_user> [--private=*true*|false]
<@{bot_user_id}> hangout-party <group_size> <party_discription> [--private=*true*|false]
"""
def analyze_user(target:str):
    return f"test for {target}"


@app.event("app_mention")
def handle_app_mention(event: dict, say: Say, client: slack_sdk.web.client.WebClient=None) -> None:
    bot_user_id = app.client.auth_test()["user_id"]
    # parse command
    user = event["user"]
    text = event.get("text", "help")
    thread_ts = event.get("thread_ts") or event.get("ts")
    text_arr = text.split()
    text_arr.remove(f"<@{bot_user_id}>")
    for idx, text in enumerate( text_arr):
        if "=" in text:
            key, value = text.split("=", 1)
            text_arr[idx] = {key:value}
    private = True
    if len(text_arr) == 0 or text_arr[0] == 'help': # show help
        reply_text = f"<@{user}> Here are the available commands:\n{help_message(bot_user_id)}"
    elif text_arr[0] == "analyze-user":
        opts, args = getopt.getopt(text_arr[1:], 'hp:', ['help', 'private='])
        help_msg = f'<@{user}> Here is the help for analyze-user:\n<@{bot_user_id}> analyze-user <target_user> [--private=*true*|false]'
        if args:
            reply_text = analyze_user(args[0])
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
                reply_text = f"<@{user}> Creating a hangout party for {group_size} people: {party_description}"
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
    
# @app.command('/analyze-user')
# def handle_analyze_user_command(ack, body, client, logger):
#     """
#     Handles the /analyze-user slash command.
#     It displays a summary file for the user. The message is private by default.

#     Usage: /analyze-user <target_username> [show_everyone=true|false]
#     """
    
#     ack()
#     # logger.info(body)
#     command_text = body.get('text', '').strip()
#     user_id = body['user_id']
#     channel_id = body['channel_id']
#     parts = command_text.split()
#     username = None
#     show_everyone = False 
#     params = {}
#     for part in parts:
#         logger.info(f'part:{part}')
#         if '=' in part:
#             key, value = part.split('=', 1)
#             params[key.lower()] = value.lower()
#         else:
#             if username == None:
#                 username = part
#             else:
#                 client.chat_postEphemeral(
#                     channel=channel_id,
#                     user=user_id,
#                     text=f"Invalid value for `target_username`. you can only search only one person at same time"
#                 )
#     if 'show_everyone' in params:
#         if params['show_everyone'] == 'true':
#             show_everyone = True
#         elif params['show_everyone'] != 'false': # Only check if not 'false'
#             client.chat_postEphemeral(
#                 channel=channel_id,
#                 user=user_id,
#                 text=f"Invalid value for `show_everyone`. Please use `true` or `false`."
#             )
#             return
#     if not username:
#         client.chat_postEphemeral(
#             channel=channel_id,
#             user=user_id,
#             text="Please provide a username. Usage: /analyze-user <target_username> [show_everyone=true|false]"
#         )
#         return
#     logger.info(f'username:{username}, show_everyone:{show_everyone}')
#     try:
#         # Construct the file path relative to the script's location
#         # TODO: connect to google drive instead of file systeam
#         file_path = os.path.join("./data/", username, "summary.txt")

#         # Check if the summary file exists
#         if not os.path.exists(file_path):
#             client.chat_postEphemeral(
#                 channel=channel_id,
#                 user=user_id,
#                 text=f"Sorry, I couldn't find a summary for the user '{username}' in {file_path}."
#             )
#             return

#         # Read the content of the summary file
#         with open(file_path, 'r') as f:
#             summary_content = f.read()
#         message_text = f"Here is the information for *{username}*:\n\n{summary_content}"
#         # Send the summary as an ephemeral message
#         if show_everyone:
#             requester_info = f"\n_(Analysis requested by <@{user_id}>)_"
#             client.chat_postMessage(
#                 channel=channel_id,
#                 text=message_text + requester_info
#             )
#         else: # This block runs by default
#             client.chat_postEphemeral(
#                 channel=channel_id,
#                 user=user_id,
#                 text=message_text
#             )

#     except Exception as e:
#         logger.error(f"Error handling /analyze-user command: {e}")
#         client.chat_postEphemeral(
#             channel=channel_id,
#             user=user_id,
#             text="An error occurred while processing your request. Please try again later."
#         )
#     pass    

# @app.command('hangout-party')
# def handle_hangout_party_command(awk, body, client):
#     '''
#     Usage: /hangout-party <n_users>
#     '''
#     # TODO: input a discription or sth about party, analyze all user, choose n user fittest this party
#     # TODO: open a windows to input data of party e.g. time, discription
#     pass
# Start the bot
if __name__ == "__main__":
    # Use Socket Mode Handler
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()