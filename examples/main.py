from client import DiscordClient
from models import Activity, Payload, Presence

if __name__ == "__main__":
    # discord = DiscordClient(email="EMAIL HERE", password=r"PASSWORD HERE")
    discord = DiscordClient(token="TOKEN HERE")

    @discord.on_event
    async def on_presence_update(session: DiscordClient, payload: Payload):
        # print(payload.d)
        ...

    @discord.on_event
    async def on_ready(session: DiscordClient, payload: Payload):
        print(payload.d)
        print(session.token)
        await discord.change_presence(
            Presence(
                activities=[
                    Activity(
                        applicationId="-1",
                        name="example",
                        type=2,
                    ),
                ],
                status="dnd",
            )
        )

    discord.connect()
