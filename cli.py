import argparse
from agent.agent import Agent
from agent.autonomous_agent import AutonomousAgent
from computers import (
    BrowserbaseBrowser,
    ScrapybaraBrowser,
    ScrapybaraUbuntu,
    LocalPlaywrightComputer,
    DockerComputer,
    MorphComputer,
)


# def acknowledge_safety_check_callback(message: str) -> bool:
#     response = input(
#         f"Safety Check Warning: {message}\nDo you want to acknowledge and proceed? (y/n): "
#     ).lower()
#     return response.lower().strip() == "y"


def main():
    parser = argparse.ArgumentParser(
        description="Select a computer environment from the available options."
    )
    parser.add_argument(
        "--computer",
        choices=[
            "local-playwright",
            "docker",
            "browserbase",
            "scrapybara-browser",
            "scrapybara-ubuntu",
            "morph",
        ],
        help="Choose the computer environment to use.",
        default="local-playwright",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Initial input to use instead of asking the user.",
        default=None,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for detailed output.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show images during the execution.",
    )
    parser.add_argument(
        "--start-url",
        type=str,
        help="Start the browsing session with a specific URL (only for browser environments).",
        default="https://bing.com",
    )
    args = parser.parse_args()

    computer_mapping = {
        "local-playwright": LocalPlaywrightComputer,
        "docker": DockerComputer,
        "browserbase": BrowserbaseBrowser,
        "scrapybara-browser": ScrapybaraBrowser,
        "scrapybara-ubuntu": ScrapybaraUbuntu,
        "morph": MorphComputer,
    }

    ComputerClass = computer_mapping[args.computer]

    with ComputerClass() as computer:
        system_prompt = "You are a helpful computer use agent who has exceptional software engineering skills and cause computer with great efficiency. Use firefox for browser, for coding use terminal. Solve the task specified by user and whenever stuck use the internet to help yourself."
        agent = AutonomousAgent(initial_task=args.input, computer=computer, system_prompt=system_prompt, max_steps=1000)
        items = []
        agent.start(blocking=True)

        # while True:
        #     user_input = args.input or input("> ")
        #     items.append({"role": "user", "content": user_input})
        #     output_items = agent.run_full_turn(
        #         items,
        #         print_steps=True,
        #         show_images=args.show,
        #         debug=args.debug,
        #     )
        #     items += output_items
        #     args.input = None


if __name__ == "__main__":
    main()
