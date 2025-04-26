from flask import Flask, request, jsonify
from openai import OpenAI # For connecting to OpenAI API
from flask_cors import CORS  # Import CORS
from pymongo import MongoClient
import datetime
from bson import ObjectId
from dotenv import load_dotenv
import os
import re
import string
from collections import Counter
# Load environment variables from .env file
load_dotenv()


app = Flask(__name__)
CORS(app)

api_key = os.getenv("API_KEY")
DB_CONNECTION_URL = os.getenv("DB_CONNECTION_URL")

# MongoDB connection
mongo_client = MongoClient(DB_CONNECTION_URL)
# Set up OpenAI API key
client = OpenAI()

db = mongo_client["learning_db"]  # Database name
flashcards_collection = db["flashcards"]  # Collection for flashcards
mnemonics_collection = db["mnemonics"]
stories_collection = db["stories"]
users_collection = db["users"]  # Collection for users



def preprocess_text(text):
    if not text or not isinstance(text, str):
        return ""
    
    # Define stopwords - common words that often don't add value
    stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 
                'were', 'be', 'been', 'being', 'in', 'on', 'at', 'to', 'for',
                'with', 'by', 'about', 'against', 'between', 'into', 'through',
                'during', 'before', 'after', 'above', 'below', 'from', 'up',
                'down', 'of', 'off', 'over', 'under', 'again', 'then', 'once',
                'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
                'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
                'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
                'very', 'can', 'will', 'just', 'should', 'now'}
    
    # Step 1: Remove extra whitespace
    text = ' '.join(text.split())
    
    # Step 2: Fix spacing after punctuation
    text = re.sub(r'([.,!?;:])(\w)', r'\1 \2', text)
    
    # Step 3: Remove repeated punctuation
    text = re.sub(r'([.,!?;:]){2,}', r'\1', text)
    
    # Step 4: Remove stopwords (optional, comment out if not needed)
    words = text.split()
    filtered_words = [word for word in words if word.lower() not in stopwords]
    text = ' '.join(filtered_words)
    
    # Step 5: Check for consistency in paragraph formatting
    text = re.sub(r'\n{3,}', '\n\n', text)  # Limit to max 2 newlines
    
    return text




def get_process_steps(user_input):
    """
    Generate a step-by-step explanation of a process using OpenAI.
    """
    try:
        prompt = f"""
        You are a knowledgeable science explainer. Your task is to describe the step-by-step process of "{user_input}" in a clear, structured, and educational format.

        Requirements:
        - Use **numbered steps**
        - Begin each step with a short **bold title**
        - Include **key elements or molecules** involved in each step
        - Provide a **concise explanation** (1–2 sentences) for each step

        **Output Format Example:**

        **1. Initiation**
        - **Molecule A** binds to **Enzyme X**
        - **Substrate B** transforms into **Intermediate C**
        - This step activates the reaction by initiating binding.

        **2. Conversion**
        - **Intermediate C** is modified by **Cofactor Y**
        - **Energy molecule (e.g., ATP)** is consumed
        - This transformation prepares the molecule for the next step.

        Now, explain the process of "{user_input}" following this format.
        """


        
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=500
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"

def extract_steps(text):
    """
    Extract numbered step titles from AI-generated text using regex.
    """
    step_pattern = re.findall(r"\*\*(\d+\..*?)\*\*", text)  # Extract numbered steps
    return step_pattern

def generate_mermaid_code(user_input, diagram_type="flowchart"):
    """
    Generate valid Mermaid.js code from user input.
    """
    process_text = get_process_steps(user_input)
    extracted_steps = extract_steps(process_text)

    if not extracted_steps:
        return "Error: No steps extracted."

    if diagram_type == "flowchart":
        mermaid_code = "graph TD;\n"
        nodes = []
        links = []

        for i, step in enumerate(extracted_steps):
            step_id = f"Step{i+1}"
            safe_label = step.replace('"', "'")  # Replace double quotes to avoid conflicts
            nodes.append(f'    {step_id}["{safe_label}"]')  # Add step numbering
            if i > 0:
                links.append(f"    Step{i}-->Step{i+1}")

        mermaid_code += "\n".join(nodes) + "\n" + "\n".join(links)

    elif diagram_type == "mindmap":
        mermaid_code = "mindmap\n  root((Main Topic))\n"
        for step in extracted_steps:
            safe_label = step.replace('"', "'")  # Ensure proper formatting
            mermaid_code += f'    "{safe_label}"\n'  # Correct indentation and newline

    elif diagram_type == "timeline":
        mermaid_code = "timeline\n"
        for i, step in enumerate(extracted_steps):
            safe_label = step.replace('"', "'")  # Ensure proper formatting
            mermaid_code += f'    section {i+1}\n      {safe_label}\n'



    return mermaid_code




@app.route('/generate-diagram', methods=['POST'])
def generate_diagram():
    try:
        data = request.get_json()
        input_text = data.get('input_text', '')
        diagram_type = data.get('diagram_type', 'flowchart')
        print(input_text,"##############################################")
        
        if not input_text:
            return jsonify({"error": "Please provide input text"}), 400
        
        
        
        # Extract the mermaid code from the response
        mermaid_code = generate_mermaid_code(input_text, diagram_type)

        
        # Clean up the code (remove markdown backticks if they exist)
        mermaid_code = re.sub(r'^```mermaid\s*|```$', '', mermaid_code, flags=re.MULTILINE).strip()
        
        # Convert the mermaid code to an SVG representation
        # For a real implementation, you would use a library like mermaid-cli or a service
        # Here we're just wrapping it in a div with the mermaid class for the frontend to render
        svg_representation = f'<div class="mermaid">{mermaid_code}</div>'
        
        
        return jsonify({
            "diagram_svg": svg_representation,
            "mermaid_code": mermaid_code,
            "input_text": input_text,
            "diagram_type": diagram_type
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route('/save-diagram', methods=['POST'])
# def save_diagram():
#     try:
#         data = request.get_json()
#         input_text = data.get('input_text', '')
#         diagram_svg = data.get('diagram_svg', '')
#         diagram_type = data.get('diagram_type', '')
#         user_id = data.get('user_id', '')

#         print( diagram_svg)
        
#         # Here you would save the diagram to your database
#         # This is a placeholder - implement your database logic
        
#         return jsonify({"message": f"{diagram_type.capitalize()} for '{input_text}' saved successfully!"})
        
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already exists"}), 400

    user = {
        "username": username,
        "email": email,
        "password": password,  # In a real application, make sure to hash the password
        "created_at": datetime.datetime.utcnow()
    }

    users_collection.insert_one(user)
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/user/<email>', methods=['GET'])
def get_user(email):
    try:
        # Find the user in the database
        user = users_collection.find_one({"email": email}, {'password': 0})  # Exclude the password field
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Return the user data
        return jsonify({
            "username": user.get("username"),
            "email": user.get("email"),
            "created_at": user.get("created_at")
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500





@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')


    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Find the user in the database
    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify the password
    if password == user["password"]:
        return jsonify({
            "message": "Login successful",
            "user": {
                "username": user["username"],  # Include the username in the response
                "email": user["email"],
                "user_id": str(user["_id"])  # Include the user_id in the response
            }
        })
    else:
        return jsonify({"error": "Invalid password"}), 401

@app.route('/save-flashcard', methods=['POST'])
def save_flashcard():
    data = request.get_json()
    user_id = data.get('user_id')
    front = data.get('front')
    back = data.get('back')

    if not user_id or not front or not back:
        return jsonify({"error": "user_id, front, and back are required"}), 400

    try:
        # Save the flashcard with the user_id
        flashcard = {
            "user_id": ObjectId(user_id),
            "front": front,
            "back": back,
            "created_at": datetime.datetime.utcnow()
        }
        flashcards_collection.insert_one(flashcard)
        return jsonify({"message": "Flashcard saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-flashcards/<user_id>', methods=['GET'])
def get_flashcards(user_id):
    try:
        # Convert user_id to ObjectId
        user_object_id = ObjectId(user_id)
        
        # Query flashcards for the given user_id
        flashcards = list(flashcards_collection.find({"user_id": user_object_id}))
        
        # Convert ObjectId to string for JSON serialization
        for card in flashcards:
            card["_id"] = str(card["_id"])
            if "user_id" in card:
                card["user_id"] = str(card["user_id"])
        
        return jsonify(flashcards)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/get-mnemonics/<user_id>', methods=['GET'])
def get_mnemonics(user_id):
    try:
        # Convert user_id to ObjectId
        user_object_id = ObjectId(user_id)
        
        # Query mnemonics for the given user_id
        mnemonics = list(mnemonics_collection.find({"user_id": user_object_id}))
        
        # Convert ObjectId to string for JSON serialization
        for mnemonic in mnemonics:
            mnemonic["_id"] = str(mnemonic["_id"])
            if "user_id" in mnemonic:
                mnemonic["user_id"] = str(mnemonic["user_id"])
        
        return jsonify(mnemonics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-stories/<user_id>', methods=['GET'])
def get_stories(user_id):
    try:
        # Convert user_id to ObjectId
        user_object_id = ObjectId(user_id)
        
        # Query stories for the given user_id
        stories = list(stories_collection.find({"user_id": user_object_id}))
        
        # Convert ObjectId to string for JSON serialization
        for story in stories:
            story["_id"] = str(story["_id"])
            if "user_id" in story:
                story["user_id"] = str(story["user_id"])
        
        return jsonify(stories)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete-flashcards/<card_id>', methods=['DELETE'])
def delete_flashcard(card_id):
    try:
        # Convert card_id to ObjectId
        result = flashcards_collection.delete_one({"_id": ObjectId(card_id)})
        
        if result.deleted_count == 0:
            return jsonify({"error": "Flashcard not found"}), 404
        
        return jsonify({"message": "Flashcard deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/delete-mnemonics/<mnemonic_id>', methods=['DELETE'])
def delete_mnemonic(mnemonic_id):
    try:
        # Convert mnemonic_id to ObjectId
        mnemonic_object_id = ObjectId(mnemonic_id)
        
        # Delete the mnemonic with the given _id
        result = mnemonics_collection.delete_one({"_id": mnemonic_object_id})
        
        if result.deleted_count == 0:
            return jsonify({"error": "Mnemonic not found"}), 404
        
        return jsonify({"message": "Mnemonic deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete-stories/<id>', methods=['DELETE'])
def delete_story(id, user_id):
    try:
        result = stories_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count > 0:
            return jsonify({"message": "Story deleted successfully"})
        else:
            return jsonify({"error": "Story not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save-mnemonic', methods=['POST'])
def save_mnemonic():
    data = request.get_json()
    print("#################,data",data)

    user_id = data.get('user_id')
    mnemonic = data.get('mnemonic')
    input_text = data.get('input_text')

    if not user_id or not mnemonic or not input_text:
        return jsonify({"error": "user_id, mnemonic, and input text are required"}), 400

    try:
        user_id = ObjectId(user_id)
    except errors.InvalidId:
        return jsonify({"error": "Invalid user_id"}), 400

    mnemonic_doc = {
        "user_id": user_id,
        "mnemonic": mnemonic,
        "created_at": datetime.datetime.utcnow()
    }

    mnemonics_collection.insert_one(mnemonic_doc)
    return jsonify({"message": "Mnemonic saved successfully"}), 200

@app.route('/save-story', methods=['POST'])
def save_story():
    data = request.get_json()
    user_id = data.get('user_id')
    story = data.get('story')
    input_text = data.get('input_text')

    if not user_id or not story or not input_text:
        return jsonify({"error": "user_id, story, and input text are required"}), 400

    story_doc = {
        "user_id": ObjectId(user_id),
        "input_text": input_text,
        "story": story,
        "created_at": datetime.datetime.utcnow()
    }

    stories_collection.insert_one(story_doc)
    return jsonify({"message": "Story saved successfully"}), 200

@app.route('/generate-mnemonic', methods=['POST'])
def generate_mnemonic():
    data = request.json
    input_text = data.get('input_text')  # e.g., "Order of planets"
    print(input_text)

    if not input_text:
        return jsonify({"error": "Input text are required"}), 400

    try:
        completion = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a creative and helpful assistant that generates powerful and easy-to-remember mnemonics. "
                "Your goal is to help students retain complex information through fun, meaningful, and memorable mnemonics."
            )
        },
        {
            "role": "user",
            "content": (
                f"Create a mnemonic for the following topic:\n\n"
                f"\"{input_text}\"\n\n"
                "Requirements:\n"
                "1. The mnemonic should form a memorable acronym, phrase, or sentence.\n"
                "2. Each letter (or word) in the mnemonic must correspond to a key point or concept from the topic.\n"
                "3. After the mnemonic, provide a short explanation mapping each part to what it represents.\n"
                "\n"
                "Example Format:\n"
                "**Mnemonic:** SMART\n"
                "- **S** – Specific: Define clear goals\n"
                "- **M** – Measurable: Quantify progress\n"
                "- **A** – Achievable: Set realistic goals\n"
                "- **R** – Relevant: Align with objectives\n"
                "- **T** – Time-bound: Set a deadline"
            )
        }
    ]
)


        mnemonic = completion.choices[0].message.content
        return jsonify({"mnemonic": mnemonic})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate-story', methods=['POST'])
def generate_story():
    data = request.json
    input_text = data.get('input_text')  # e.g., "Photosynthesis process"
    print(input_text)

    if not input_text:
        return jsonify({"error": "Input text are required"}), 400

    try:
        completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a creative and engaging storyteller who specializes in crafting short, vivid, and memorable stories "
                "that help users understand and recall complex information. "
                "Use imaginative characters, emotional connections, and relatable scenarios to embed key concepts into a story. "
                "The story should be short, engaging, and tied clearly to the topic."
            )
        },
        {
            "role": "user",
            "content": (
                f"Create a short, vivid story to help me remember the following concept:\n\n"
                f"\"{input_text}\"\n\n"
                "Story Guidelines:\n"
                "1. Use a central character or metaphor that represents the main idea.\n"
                "2. Include vivid sensory details (sights, sounds, feelings) to make it memorable.\n"
                "3. Embed each key point of the concept into the story clearly.\n"
                "4. Keep the story concise but emotionally engaging.\n"
                "5. Limit the story length to 300 words, but it should be meaningfull.\n\n"
                "After the story, briefly explain the meaning behind each element used, mapping it to the real concept."
            )
        }
    ],
    max_tokens=600
)


        story = completion.choices[0].message.content
        return jsonify({"story": story})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-flashcard', methods=['POST'])
def generate_flashcard():
    data = request.json
    user_id = data.get('user_id')
    input_text = data.get('input_text')  # e.g., "Photosynthesis"
    print(input_text)

    if not user_id or not input_text:
        return jsonify({"error": "user_id and input text are required"}), 400

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates efficient and concise flashcards. The front of the flashcard should contain a question or term, and the back should contain a clear and concise answer or explanation. Keep the content brief and to the point."},
                {"role": "user", "content": f"Create a flashcard for: {input_text}"}
            ],
            max_tokens=100
        )

        flashcard_content = completion.choices[0].message.content

        if "Front:" in flashcard_content and "Back:" in flashcard_content:
            front = flashcard_content.split("Front:")[1].split("Back:")[0].strip()
            back = flashcard_content.split("Back:")[1].strip()
        else:
            front = input_text
            back = flashcard_content

        flashcard = {
            "user_id": ObjectId(user_id),
            "front": front,
            "back": back,
            "created_at": datetime.datetime.utcnow()
        }

        flashcards_collection.insert_one(flashcard)
        return jsonify({"flashcard": {"front": front, "back": back}})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-summary', methods=['POST'])
def summarize_content():
    data = request.json
    input_text = data.get('input_text')
    print(input_text)

    if not input_text:
        return jsonify({"error": "Input text are required"}), 400

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes content. Provide a concise and clear gist of the input text, capturing the main points in a few sentences."},
                {"role": "user", "content": f"Summarize the following content: {input_text}"}
            ],
            max_tokens=100
        )

        summary = completion.choices[0].message.content
        
        original_length = len(input_text)
        summary_length = len(summary)
        
        key_points = len([s for s in summary.split('.') if s.strip()])
        
        reduction_percent = int(((original_length - summary_length) / original_length) * 100) if original_length > 0 else 0

        stats = {
            "originalLength": original_length,
            "summaryLength": summary_length,
            "keyPoints": key_points,
            "reductionPercent": reduction_percent
        }

        return jsonify({
            "summary": summary,
            "stats": stats
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-mcqs', methods=['POST'])
def generate_mcqs():
    data = request.json
    input_text = data.get('input_text')  # e.g., "A paragraph about photosynthesis"
    print("Input Text:", input_text)

    if not input_text:
        return jsonify({"error": "Input text are required"}), 400

    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates multiple-choice questions (MCQs) from a given paragraph. For each question, provide 4 options and indicate the correct answer. Ensure the questions are clear, relevant, and the options are plausible. Format your response as follows:\n\nQuestion: <question>\nOptions:\nA. <option1>\nB. <option2>\nC. <option3>\nD. <option4>\nCorrect Answer: <correct option letter>"},
                {"role": "user", "content": f"Generate multiple-choice questions from the following paragraph: {input_text}"}
            ],
            max_tokens=500
        )

        mcqs_text = completion.choices[0].message.content
        print("Raw API Response:", mcqs_text)

        mcqs = []
        
        for question_block in mcqs_text.split("\n\n"):
            if "Question:" in question_block and "Options:" in question_block and "Correct Answer:" in question_block:
                lines = question_block.split("\n")
                
                question_line = next((line for line in lines if line.startswith("Question:")), "")
                question = question_line.replace("Question:", "").strip()
                
                options = []
                for line in lines:
                    if line.strip().startswith(("A.", "B.", "C.", "D.")):
                        options.append(line.strip())
                
                correct_answer_line = next((line for line in lines if line.startswith("Correct Answer:")), "")
                correct_answer = correct_answer_line.replace("Correct Answer:", "").strip()
                
                if question and options and correct_answer:
                    mcqs.append({
                        "question": question,
                        "options": options,
                        "correct_answer": correct_answer
                    })

        print("Parsed MCQs:", mcqs)
        return jsonify({"mcqs": mcqs})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/keyword-mnemonic', methods=['POST'])
def generate_keyword_mnemonic():
    try:
        data = request.json
        input_text = data.get('input_text')  # e.g., "A paragraph about photosynthesis"
        processed_text = preprocess_text(input_text)

        if not input_text:
            return jsonify({"success": False, "error": "Input text are required"}), 400


        response = client.chat.completions.create(
            model="ft:gpt-3.5-turbo-0125:bodhiment::BP99r8So",
            messages=[
                {"role": "system", "content": "You are an educational assistant that creates memorable mnemonics to help users learn concepts."},
                {"role": "user", "content": processed_text}
            ]
        )

        mnemonic = response.choices[0].message.content

        return jsonify({"success": True, "mnemonic": mnemonic})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 if PORT is not set
    app.run(host='0.0.0.0', port=port)
    app.run(debug=True)
