package com.checkmate.app.network

import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

// 10.0.2.2 is the Android EMULATOR's alias for the host machine's own localhost — use this
// while the backend runs on the same laptop (`uvicorn app.main:app --port 8000`).
//
// Testing on a PHYSICAL phone instead? Two changes needed:
//   1. Start the backend with `uvicorn app.main:app --host 0.0.0.0 --port 8000` (so it
//      accepts connections from other devices, not just the loopback interface).
//   2. Put the phone on the same Wi-Fi as the laptop and change BASE_URL below to
//      "http://<laptop-lan-ip>:8000/" (find the IP with `ipconfig` on the laptop).
private const val BASE_URL = "http://10.0.2.2:8000/"

object ApiClient {
    val service: ApiService by lazy {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(60, TimeUnit.SECONDS)
            .readTimeout(180, TimeUnit.SECONDS) // OCR/grading calls can genuinely take a while
            .writeTimeout(180, TimeUnit.SECONDS)
            .build()

        val gson = GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .create()

        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }
}
