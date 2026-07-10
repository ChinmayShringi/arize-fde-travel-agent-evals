from agent.loop import run_agent


def main():
    print("Travel Agent — ask me about flights, hotels, weather, or trip plans.")
    print("Type 'quit' to exit.\n")
    messages = []
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            break
        messages.append({"role": "user", "content": user_input})
        reply, messages = run_agent(messages)
        print(f"\nagent> {reply}\n")


if __name__ == "__main__":
    main()
