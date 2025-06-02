from firebase_admin import firestore
import json
import os
from typing import List
from pydantic import BaseModel, Field
from groq import Groq
from dotenv import load_dotenv
import instructor
from datetime import datetime

from Helpers.ExtractTextFromEditor import extract_text_from_rich_content

load_dotenv()


class QuestionClass(BaseModel):
    question: str
    options: list[str] = Field(..., min_items=4, max_items=4)
    answer: str


class QuizResponseModel(BaseModel):
    questions: List[QuestionClass]


def GetCourseTextContentByChapters(course_id):
    try:
        db = firestore.client()
        chapters_ref = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
        chapters_docs = chapters_ref.stream()

        course_text_content = []
        for doc in chapters_docs:
            chapter_data = doc.to_dict()
            content = chapter_data.get("content")
            if content:
                parsed = json.loads(content)
                text_content = extract_text_from_rich_content(parsed)
                course_text_content.append(text_content)

        if not course_text_content:
            return {"error": "No text content found for this course"}, 404

        concatenated_text = " ".join(course_text_content)
        return concatenated_text
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def generate_quiz(name: str, subject: str, num_questions: int) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    client = instructor.from_groq(client, mode=instructor.Mode.TOOLS)

    # Prompt for the LLM to generate a specific number of questions
    prompt = f"""
    Generate a quiz titled '{name}' for the subject '{subject}'.
    Return {num_questions} questions ONLY in JSON format.

    Each question must include:
    - question: a string
    - options: a list of 4 answer choices (A, B, C, D)
    - answer: the correct option (must match one of the 4 options)
    - explanation: the explanation for the answer

    Format:
    {{
      "questions": [
        {{
          "question": "...",
          "options": ["...", "...", "...", "..."],
          "answer": "...",
          "explanation" : "..."
        }},
        ...
      ]
    }}
    """

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model='llama3-70b-8192',
        response_model=QuizResponseModel
    )

    # Return as dictionary (can be dumped to JSON)
    return response.model_dump()


def create_and_save_quiz(course_id: str, title: str, passing_score: int = 7, chapter_id: str = None):
    db = firestore.client()

    chapters_ref = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
    chapters_docs = chapters_ref.stream()

    combined_questions = []
    for chapter_doc in chapters_docs:
        chapter_data = chapter_doc.to_dict()
        chapter_title = chapter_data.get("title")
        chapter_text_content = extract_text_from_rich_content(json.loads(chapter_data.get("content", "{}")))

        # Generate 3 or 4 questions for each chapter
        num_questions = 3 if len(chapter_text_content.split()) < 500 else 4
        quiz_data = generate_quiz(name=f"{title} - {chapter_title}", subject=chapter_text_content,
                                  num_questions=num_questions)
        print(quiz_data)
        # Append the questions from the current chapter to the combined list
        combined_questions.extend(quiz_data["questions"])

    now = datetime.utcnow().isoformat()

    quiz_doc = {
        "courseId": course_id,
        "chapterId": chapter_id,
        "questions": combined_questions,
        "passingScore": passing_score,
        "createdAt": now,
        "updatedAt": now
    }

    # Remove chapterId if not provided
    if chapter_id is None:
        quiz_doc.pop("chapterId")

    # Check if a quiz already exists for this course (and chapter if provided)
    quizzes_ref = db.collection("quizzes")
    query = quizzes_ref.where("courseId", "==", course_id)
    existing_quizzes = list(query.stream())

    if existing_quizzes:
        # Update the first found quiz
        quiz_ref = existing_quizzes[0].reference
        # Keep original createdAt if present
        existing_data = existing_quizzes[0].to_dict()
        quiz_doc["createdAt"] = existing_data.get("createdAt", now)
        # Remove previous questions and set new ones
        quiz_ref.update({
            "questions": [],  # Clear previous questions first
        })
        quiz_ref.update(quiz_doc)
    else:
        # Save to Firestore
        quizzes_ref.add(quiz_doc)

    return quiz_doc



def get_quizzes_by_course(course_id: str):
    db = firestore.client()
    quizzes_ref = db.collection("quizzes").where("courseId", "==", course_id)
    quizzes = [doc.to_dict() | {"id": doc.id} for doc in quizzes_ref.stream()]
    if not quizzes:
        return {"error": "No quizzes found for this course"}, 404
    return quizzes