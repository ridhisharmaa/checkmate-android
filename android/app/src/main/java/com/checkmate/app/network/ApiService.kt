package com.checkmate.app.network

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface ApiService {

    // --- Auth ---

    @POST("auth/signup")
    suspend fun signup(@Body body: SignupRequest): TokenResponse

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @GET("auth/me")
    suspend fun me(): TeacherResponse

    // --- Exams & roster ---

    // title/subject are plain form fields (FastAPI Form(...)), not JSON — hence RequestBody
    // parts here rather than a @Body, matching how the backend route declares them.
    @Multipart
    @POST("exams")
    suspend fun createExam(
        @Part("title") title: RequestBody,
        @Part("subject") subject: RequestBody,
        @Part answerKeyFiles: List<MultipartBody.Part>,
    ): ExamSummary

    @GET("exams")
    suspend fun listExams(): List<ExamSummary>

    @GET("exams/{examId}")
    suspend fun getExam(@Path("examId") examId: String): ExamDetailResponse

    @POST("exams/{examId}/roster/range")
    suspend fun addRollRange(@Path("examId") examId: String, @Body body: RollRangeRequest): List<StudentSummary>

    @POST("exams/{examId}/roster")
    suspend fun addRollNumber(@Path("examId") examId: String, @Body body: AddRollNumberRequest): StudentSummary

    @DELETE("exams/{examId}/roster/{studentId}")
    suspend fun removeRollNumber(@Path("examId") examId: String, @Path("studentId") studentId: String): Response<Unit>

    // --- Submissions ---

    @Multipart
    @POST("exams/{examId}/students/{studentId}/submission")
    suspend fun createSubmission(
        @Path("examId") examId: String,
        @Path("studentId") studentId: String,
        @Part studentFiles: List<MultipartBody.Part>,
    ): SubmissionCreateResponse

    @GET("jobs/{jobId}")
    suspend fun getJob(@Path("jobId") jobId: String): JobStatusResponse

    @GET("submissions/{submissionId}")
    suspend fun getSubmission(@Path("submissionId") submissionId: String): SubmissionDetailResponse

    @PATCH("submissions/{submissionId}/questions/{questionId}")
    suspend fun overrideQuestion(
        @Path("submissionId") submissionId: String,
        @Path("questionId") questionId: String,
        @Body body: QuestionOverridePatchRequest,
    ): SubmissionDetailResponse
}
