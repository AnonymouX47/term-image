import os
import dotenv
import discord
import json

from typing import List, Optional, Dict

secrets = dotenv.load_dotenv()
bot_token = os.environ.get("DISCORD_TOKEN")

class JsonDatabase(object):
    def __init__(self, filename):
        self.path = os.path.join(os.path.dirname(__file__), filename)
        self.content = self.setup()

    def add(self, created_by, task):
        if created_by not in self.content:
            self.content.setdefault(created_by, [])
        self.content[created_by].append(task)
        self.write_file(json.dumps(self.content))

    def setup(self) -> Dict:
        if not os.path.isfile(self.path):
            self.write_file(json.dumps({}))
            return {}
        return self.read_file_content()

    def read_file_content(self):
        with open(self.path, "r") as reader:
            file_content = reader.read()
            json_data = json.loads(file_content)
            return json_data  

    def write_file(self, content:str):
        with open(self.path, "w") as writer:
            writer.write(content)

class CommandParser(object):
    def __init__(self, message:discord.Message):
        self.message = message
        self.database = JsonDatabase("tasks")

    def create_parser(self):
        command, parameters = self.__parse_message()
        return self.message.channel.send("jeje")

    def __parse_message(self):
        slices:List[str] = self.message.content.split(" ")
        command, parameters = "", []
        for index, argument in enumerate(slices):
            if index == 0:
                current_slices:List[str] = argument.split(".")
                is_task_message = current_slices[0] == "task"
                task_command:Optional[str] = ".".join(current_slices[1:]).strip()
                if is_task_message:
                    command = task_command
                continue
            parameters.append(argument)
        return command, parameters

class Error(object):
    @staticmethod
    async def create_error(title, channel, description=None, color=discord.Colour(0xff0000)):
        embed = discord.Embed(title=title, description=description, color=color)
        await channel.send(embed=embed)

class TaskBotClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        command_parser = CommandParser(message)
        await command_parser.create_parser()

client = TaskBotClient()
client.run(bot_token)
