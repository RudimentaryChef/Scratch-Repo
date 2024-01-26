from unity_socket import execute_action
from unity_socket import get_state


def main():
    unity_url = "ws://localhost:4649/hmt/{}".format("giant")
    htn = Htn()

    while True:
        # Get state
        state = get_state(unity_url)
        # Convert state to shop2 format
        wm = convert_state(state)
        # Run htn on state
        wm = run_htn(wm, htn)
        # Collect Sais from WM (should only be one)
        sais = [i for i in wm if i[0] == "sai"]
        # Apply SAIs to unity game
        execute_action(unity_url, sais[0][-1])


# Produces list of shop2 tuples
def convert_state(state):
    return state


if __name__ == "__main__":
    main()