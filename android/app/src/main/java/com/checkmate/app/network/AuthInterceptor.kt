package com.checkmate.app.network

import okhttp3.Interceptor
import okhttp3.Response

/** Attaches the stored teacher JWT to every request, when one exists. Requests made
 * before login (signup/login themselves) simply have no token to attach yet. */
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = TokenStore.getToken() ?: return chain.proceed(original)
        val authorized = original.newBuilder()
            .header("Authorization", "Bearer $token")
            .build()
        return chain.proceed(authorized)
    }
}
