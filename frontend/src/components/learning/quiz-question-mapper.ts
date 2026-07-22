export interface QuizQuestionPayload {
  id: string;
  question_type: string;
  question_body: string;
  options?: Array<{ key: string; value: string }>;
  knowledge_points?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  difficulty_level?: "beginner" | "intermediate" | "advanced";
}

export interface MappedQuizQuestion {
  id: string;
  type: "CHOICE" | "MULTIPLE_CHOICE" | "FILL_BLANK";
  body: string;
  options?: Array<{ key: string; value: string }>;
  knowledgePoints?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced";
  subject?: string;
}

/** Converts both content API difficulty field spellings into the quiz UI shape. */
export function mapQuizQuestion(payload: QuizQuestionPayload, subject?: string): MappedQuizQuestion | null {
  if (payload.question_type !== "CHOICE" && payload.question_type !== "MULTIPLE_CHOICE" && payload.question_type !== "FILL_BLANK") {
    return null;
  }

  return {
    id: String(payload.id),
    type: payload.question_type,
    body: payload.question_body,
    options: payload.options,
    knowledgePoints: payload.knowledge_points,
    difficulty: payload.difficulty ?? payload.difficulty_level,
    subject,
  };
}
