import os
import logging
from datetime import datetime, timedelta
import uuid

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

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

@app.command('/analyze-user')
def handle_analyze_user_command(ack, body, client, logger):
    """
    Handles the /analyze-user slash command.
    It displays a summary file for the user. The message is private by default.

    Usage: /analyze-user <target_username> [show_everyone=true|false]
    """
    
    ack()
    # logger.info(body)
    command_text = body.get('text', '').strip()
    user_id = body['user_id']
    channel_id = body['channel_id']
    parts = command_text.split()
    username = None
    show_everyone = False 
    params = {}
    for part in parts:
        logger.info(f'part:{part}')
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.lower()] = value.lower()
        else:
            if username == None:
                username = part
            else:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text=f"Invalid value for `target_username`. you can only search only one person at same time"
                )
    if 'show_everyone' in params:
        if params['show_everyone'] == 'true':
            show_everyone = True
        elif params['show_everyone'] != 'false': # Only check if not 'false'
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Invalid value for `show_everyone`. Please use `true` or `false`."
            )
            return
    if not username:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Please provide a username. Usage: /analyze-user <target_username> [show_everyone=true|false]"
        )
        return
    logger.info(f'username:{username}, show_everyone:{show_everyone}')
    try:
        # Construct the file path relative to the script's location
        # TODO: connect to google drive instead of file systeam
        file_path = os.path.join("./data/", username, "summary.txt")

        # Check if the summary file exists
        if not os.path.exists(file_path):
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Sorry, I couldn't find a summary for the user '{username}' in {file_path}."
            )
            return

        # Read the content of the summary file
        with open(file_path, 'r') as f:
            summary_content = f.read()
        message_text = f"Here is the information for *{username}*:\n\n{summary_content}"
        # Send the summary as an ephemeral message
        if show_everyone:
            requester_info = f"\n_(Analysis requested by <@{user_id}>)_"
            client.chat_postMessage(
                channel=channel_id,
                text=message_text + requester_info
            )
        else: # This block runs by default
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=message_text
            )

    except Exception as e:
        logger.error(f"Error handling /analyze-user command: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="An error occurred while processing your request. Please try again later."
        )
    pass    

@app.command('hangout-party')
def handle_hangout_party_command(awk, body, client):
    '''
    Usage: /hangout-party <n_users>
    '''
    # TODO: input a discription or sth about party, analyze all user, choose n user fittest this party
    # TODO: open a windows to input data of party e.g. time, discription
    pass
# Start the bot
if __name__ == "__main__":
    # Use Socket Mode Handler
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()