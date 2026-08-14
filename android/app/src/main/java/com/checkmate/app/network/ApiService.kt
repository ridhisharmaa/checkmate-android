package com.checkmate.app.network

import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.Part
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {

    // Each MultipartBody.Part is created with the same field name ("teacher_files" /
    // "student_files"), matching FastAPI's `list[UploadFile] = File(...)` on the other end.
    @Multipart
    @POST("submissions")
    suspend fun createSubmission(
        @Part teacherFiles: List<MultipartBody.Part>,
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
