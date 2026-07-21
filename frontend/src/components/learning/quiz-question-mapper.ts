export interface QuizQuestionPayload {
  id: string;
  question_type: "CHOICE" | "MULTIPLE_CHOICE" | "FILL_BLANK" | string;
  question_body: string;
  options?: Array<{ key: string; value: string }>;
  correct_answer: string;
  explanation?: string;
  knowledge_points?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  difficulty_level?: "beginner" | "intermediate" | "advanced";
}

export interface MappedQuizQuestion {
  id: string;
  type: "CHOICE" | "MULTIPLE_CHOICE" | "FILL_BLANK";
  body: string;
  options?: Array<{ key: string; value: string }>;
  correctAnswer: string;
  explanation?: string;
  knowledgePoints?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  subject?: string;
}

/** Converts both content API difficulty field spellings into the quiz UI shape. */
export function mapQuizQuestion(payload: QuizQuestionPayload, subject?: string): MappedQuizQuestion {
  return {
    id: String(payload.id),
    type: payload.question_type as MappedQuizQuestion["type"],
    body: payload.question_body,
    options: payload.options,
    correctAnswer: payload.correct_answer,
    explanation: payload.explanation,
    knowledgePoints: payload.knowledge_points,
    difficulty: payload.difficulty ?? payload.difficulty_level,
    subject,
  };
}
