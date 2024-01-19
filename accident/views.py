from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

import openai
import time
import json

GLOBAL_VAR_CLIENT = ""
GLOBAL_VAR_ASSISTANT = ""
GLOBAL_VAR_THREAD = ""

def format_for_gpt4(run_steps):
    formatted_output = ""
    for step in run_steps.data:
        if step.type == "tool_calls":
            for output in step.step_details.tool_calls[0].code_interpreter.outputs:
                if hasattr(output, 'logs'):
                    formatted_output += output.logs + "\n"
                elif hasattr(output, 'image'):
                    formatted_output += "[Image output not displayed]\n"
            formatted_output += "\n"
    return formatted_output


def construct_gpt_prompt(formatted_output, user_input):
    prompt = "Analysis based on the auto accident dataset:\n"
    prompt += formatted_output
    prompt += "\nUser Query: " + user_input
    prompt += "\nPlease provide further analytical insights or answer specific questions."
    return prompt


def run_code_interpreter(client, assistant_id, thread_id, user_input):
    # Add user input to the thread
    try:
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )
    except Exception as e:
        print(f"An error occurred while adding message to the thread: {e}")
        return ""

    # Create a new run based on the updated thread
    try:
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        # Wait for the run to complete
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id)
            if run_status.status == "completed":
                break
            time.sleep(5)  # Check every 5 seconds
        # Retrieve run steps
        run_steps = client.beta.threads.runs.steps.list(
            thread_id=thread_id, run_id=run.id)

        # Print the raw output for debugging
        print("Raw Output from Code Interpreter:")
        for step in run_steps.data:
            if step.type == "tool_calls":
                for output in step.step_details.tool_calls[0].code_interpreter.outputs:
                    if hasattr(output, 'logs'):
                        print(output.logs)
                    elif hasattr(output, 'image'):
                        print("[Image output not displayed]")

        return format_for_gpt4(run_steps)
    except Exception as e:
        print(f"An error occurred while running Code Interpreter: {e}")
        return ""


def query_gpt4(client, model, messages):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"


@api_view(['GET'])
def hello_world(request):
    return Response({'message': 'Hello, world!'})


@api_view(['POST'])
def get_file_analysis(request):
    file = request.FILES.get("file")

    # print(file.read())

    openai.api_key = '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'
    global GLOBAL_VAR_CLIENT 
    global GLOBAL_VAR_ASSISTANT
    global GLOBAL_VAR_THREAD

    GLOBAL_VAR_CLIENT = openai.OpenAI(api_key=openai.api_key)

    model = "gpt-4-1106-preview"

    dataset_file = GLOBAL_VAR_CLIENT.files.create(file=file.read(), purpose='assistants')

    try:
        GLOBAL_VAR_ASSISTANT = GLOBAL_VAR_CLIENT.beta.assistants.create(
            instructions="You are an auto insurance claims specialist. When given a file, please analyze the type of file and what the file can do.",
            # model="gpt-4-1106-preview",
            model="gpt-3.5-turbo-1106",
            tools=[{"type": "code_interpreter"}],
            file_ids=[dataset_file.id]
        )
    except Exception as e:
        print(f"An error occurred while creating the Assistant: {e}")
        return

    try:
        GLOBAL_VAR_THREAD = GLOBAL_VAR_CLIENT.beta.threads.create(messages=[{
            "role": "user",
            "content": "Using the dataset, identify the most common causes of accidents, trends over time, and correlations between different types of incidents."
        }])
    except Exception as e:
        print(f"An error occurred while creating the thread: {e}")
        return

    try:
        run = GLOBAL_VAR_CLIENT.beta.threads.runs.create(
            thread_id=GLOBAL_VAR_THREAD.id, assistant_id=GLOBAL_VAR_ASSISTANT.id)
    except Exception as e:
        print(f"An error occurred while running the Assistant: {e}")
        return

    while True:
        try:
            run_status = GLOBAL_VAR_CLIENT.beta.threads.runs.retrieve(
                thread_id=GLOBAL_VAR_THREAD.id, run_id=run.id)
            if run_status.status == "completed":
                print("Analysis complete.")
                break
            else:
                print("ADAPT AI is still analysing...")
                time.sleep(5)
        except Exception as e:
            print(f"An error occurred while checking run status: {e}")
            return

    try:
        run_steps = GLOBAL_VAR_CLIENT.beta.threads.runs.steps.list(
            thread_id=GLOBAL_VAR_THREAD.id, run_id=run.id)
        formatted_output = format_for_gpt4(run_steps)
    except Exception as e:
        print(f"An error occurred while retrieving run steps: {e}")
        return

    gpt_prompt = construct_gpt_prompt(formatted_output, "")
    initial_messages = [{"role": "system", "content": "You are an auto insurance claim specialist with knowledge of analysing auto claims and car crashes."},
                        {"role": "user", "content": gpt_prompt}]

    gpt_response = query_gpt4(GLOBAL_VAR_CLIENT, model, initial_messages)
    print("ADPAT AI Response:")
    print(gpt_response)

    return Response({'message': gpt_response})


@api_view(['POST'])
def get_answer(request):
    messages = [{"role": "system", "content": "You are an auto insurance claim specialist with knowledge of analysing auto claims and car crashes. You can suggest the exact & perfect answer as possible as you can for the custom questions. The answer can be short but not too short if the information is mandatory."}]
    user_input = request.data.get("question")

    model = "gpt-3.5-turbo-1106"
    global GLOBAL_VAR_CLIENT
    global GLOBAL_VAR_ASSISTANT
    global GLOBAL_VAR_THREAD

    print(user_input)

    # Run Code Interpreter on user input
    code_interpreter_output = run_code_interpreter(
        GLOBAL_VAR_CLIENT, GLOBAL_VAR_ASSISTANT.id, GLOBAL_VAR_THREAD.id, user_input)
    if code_interpreter_output.strip():
        # Use GPT-4 to analyze the output of Code Interpreter
        gpt_prompt = construct_gpt_prompt(code_interpreter_output, user_input)
        messages.append({"role": "user", "content": gpt_prompt})
    else:
        # Directly ask GPT-4 the user's question
        messages.append({"role": "user", "content": user_input})

    gpt_response = query_gpt4(GLOBAL_VAR_CLIENT, model, messages)
    return Response({'message': gpt_response})
