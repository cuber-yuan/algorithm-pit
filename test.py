from app.tank2_judge import TankBotInterface
from app.tank2_judge import Action

if __name__ == "__main__":
    interface = TankBotInterface()
    json = interface.send_to_client(True, 0)
    print(json)