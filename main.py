import os
import dotenv
import discord
import json
import time

from typing import List, Optional, Dict, Tuple

secrets = dotenv.load_dotenv()
bot_token = os.environ.get("DISCORD_TOKEN")


class JsonDatabase(object):
    def __init__(self, filename: str):
        self.path = os.path.join(os.path.dirname(__file__), filename)
        self.content = self.setup()

    def add(self, created_by: int, task: str, created_at: int) -> None:
        if not self.content.get(str(created_by)):
            self.content.setdefault(str(created_by), [])
        self.content[str(created_by)].append(task)
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

    def write_file(self, content: str) -> None:
        with open(self.path, "w") as writer:
            writer.write(content)


class CommandParser(object):
    def __init__(self, message: discord.Message):
        self.message = message
        self.database: Dict[str, List[str]] = JsonDatabase("tasks")

    def create_parser(self):
        command, parameters = self.__parse_message()
        if command == "create":
            task = " ".join(parameters)
            created_by = int(time.time())
            self.database.add(self.message.author.id, task, created_by)
            return self.message.channel.send(f"Created a task at <t:{created_by}>")
        elif command == "list":
            tasks: List[str] = self.get_task_list(self.message.author.id)
            description = ""
            print(tasks)
            for index, element in enumerate(tasks):
                description += f"**{element}**\n"

            return self.message.channel.send(
                embed=discord.Embed(title="Tasks", description=description)
            )
        return self.message.channel.send("ll")

    def get_task_list(self, author_id: int) -> List[str]:
        task_author_id = str(self.message.author.id)
        if task_author_id not in self.database.content:
            return []
        return self.database.content.get(task_author_id)

    def __parse_message(self) -> Tuple[str, List[str]]:
        slices: List[str] = self.message.content.split(" ")
        command, parameters = "", []
        for index, argument in enumerate(slices):
            if index == 0:
                current_slices: List[str] = argument.split(".")
                is_task_message = current_slices[0] == "task"
                task_command: Optional[str] = ".".join(current_slices[1:]).strip()
                if is_task_message:
                    command = task_command
                continue
            parameters.append(argument)
        return command, parameters


class Error(object):
    @staticmethod
    async def create_error(
        title: str, channel, description=None, color=discord.Colour(0xFF0000)
    ):
        embed = discord.Embed(title=title, description=description, color=color)
        await channel.send(embed=embed)


class TaskBotClient(discord.Client):
    async def on_ready(self):
        print("Logged on as {0}!".format(self.user))

    async def on_message(self, message: discord.Message):
        command_parser = CommandParser(message)
        await command_parser.create_parser()


client = TaskBotClient()
client.run(bot_token)
