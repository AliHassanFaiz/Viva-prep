"""Practice modes. One place that defines how the examiner, grader and copy change per mode."""
from typing import Literal

Mode = Literal["viva", "interview"]
DEFAULT_MODE: Mode = "viva"

MODES: dict[str, dict] = {
    "viva": {
        "examiner": "a university examiner conducting a spoken viva",
        "person": "student",
        "source": "report",
        "session": "mock viva",
        "probes": [
            "research objective and problem statement",
            "methodology and design choices",
            "results and evaluation",
            "limitations and future work",
            "dataset, system architecture or implementation",
        ],
        "rubric": {
            "accuracy": "are the student's claims consistent with the report passages?",
            "justification": "does the student give reasons and evidence, not only statements?",
        },
    },
    "interview": {
        "examiner": "an experienced interviewer running a spoken job interview",
        "person": "candidate",
        "source": "document (resume, job description, project notes or similar)",
        "session": "mock interview",
        "probes": [
            "key projects, responsibilities and achievements",
            "technical skills, tools and technologies used",
            "problem solving, challenges and how they were handled",
            "results, impact and measurable outcomes",
            "role requirements, qualifications and motivation",
        ],
        "rubric": {
            "accuracy": "are the candidate's claims consistent with the document passages and relevant to the question?",
            "justification": "does the candidate give concrete examples, actions and results (situation, action, result), not only statements?",
        },
    },
}


def get_mode(name: str | None) -> dict:
    return MODES.get(name or DEFAULT_MODE, MODES[DEFAULT_MODE])


def norm_mode(name: str | None) -> str:
    return name if name in MODES else DEFAULT_MODE
