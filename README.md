# telegram-playlist-bot
Telegram bot that lets you create and share music playlists with friends.

# Telegram Music Bot

This is a Telegram bot that allows users to create and manage music playlists. Users can create playlists, add music to them, share playlists with others, and listen to their favorite songs directly within Telegram.

## Features

-   Create new playlists
-   Add music to existing playlists
-   View all your playlists
-   Share playlists with other users via a unique link
-   Send all music from a playlist
-   Delete specific songs from a playlist
-   Delete entire playlists
-   Help command to list available commands

## Technologies Used

-   Python 3.7+
-   aiogram 3.x
-   JSON for data storage
-   uuid for unique playlist IDs

## Setup

### Prerequisites

-   Python 3.7+
-   Telegram Bot Token

### Installation

1.  Clone the repository:

```sh
git clone [repository URL]
cd [repository directory]
```
2. Install the required packages:
```
# filepath: /Users/aghorbanmehr/Desktop/Bot.py
TOKEN = "Your Bot Token" # Replace with your actual bot token
```
3. Set up your bot token:
Replace "Your Bot Token" with your actual bot token in the TOKEN variable in Bot.py.

Usage
1. Run the bot:
```
python Bot.py
```
2. Interact with the bot on Telegram using the available commands.

Commands
/start: Starts the bot and displays the main menu.
➕ Create Playlist: Creates a new playlist.
🎵 Add Music: Adds music to a playlist.
🎶 My Playlists: Views your playlists.
/list_playlists [user_id]: Lists playlists of a specific user (for admin use).
❓ Help: Displays the help message.
Data Storage
The bot uses a music_data.json file to store user data, including playlists and songs.

Contributing
Feel free to contribute to the project by submitting pull requests, reporting issues, or suggesting new features.
