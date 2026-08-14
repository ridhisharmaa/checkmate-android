package com.checkmate.app.network

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

fun uriToMultipart(context: Context, uri: Uri, partName: String): MultipartBody.Part {
    val resolver = context.contentResolver
    val bytes = resolver.openInputStream(uri)?.use { it.readBytes() } ?: ByteArray(0)
    val mimeType = resolver.getType(uri) ?: "application/octet-stream"
    val filename = queryDisplayName(context, uri) ?: "upload_${System.currentTimeMillis()}"
    val requestBody = bytes.toRequestBody(mimeType.toMediaTypeOrNull())
    return MultipartBody.Part.createFormData(partName, filename, requestBody)
}

private fun queryDisplayName(context: Context, uri: Uri): String? {
    var name: String? = null
    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (idx >= 0 && cursor.moveToFirst()) name = cursor.getString(idx)
    }
    return name
}
