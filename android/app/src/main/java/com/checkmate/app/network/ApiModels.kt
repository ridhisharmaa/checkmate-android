package com.checkmate.app.network

// Mirrors backend/app/schemas/api.py and backend/app/schemas/grading.py exactly.
// Gson is configured (see ApiClient) with LOWER_CASE_WITH_UNDERSCORES field naming,
// so these camelCase properties map to the backend's snake_case JSON automatically —
// no @SerializedName needed as long as the names below match the Python fields.

data class SubmissionCreateResponse(
    val submissionId: String,
    val jobId: String,
)

data class JobStatusResponse(
    val jobId: String,
    val status: String,
    val currentStage: String?,
    val errorMessage: String?,
)

data class SubmissionDetailResponse(
    val submissionId: String,
    val status: String,
    val result: SubmissionResult?,
)

data class OverviewSummary(
    val strengths: List<String>,
    val watchFor: List<String>,
)

data class QuestionGradeResult(
    val id: String?, // QuestionResult row id — required for the PATCH override call
    val unitId: String,
    val path: List<String>,
    val label: String,
    val questionText: String,
    val modelAnswer: String,
    val studentAnswer: String?,
    val attempted: Boolean,
    val maxMarks: Double,
    val similarityScore: Double?,
    val llmScorePct: Double?,
    val finalScore: Double,
    val feedback: String,
    val countedTowardTotal: Boolean,
    val teacherOverride: String?,
    val hasDiagram: Boolean,
    val hasTable: Boolean,
    val hasCode: Boolean,
)

data class SubmissionResult(
    val overview: OverviewSummary,
    val handwritingConfidence: Double,
    val results: List<QuestionGradeResult>,
    val totalScore: Double,
    val maxScore: Double,
    val gradeLetter: String,
)

data class QuestionOverridePatchRequest(
    val override: String,
)
