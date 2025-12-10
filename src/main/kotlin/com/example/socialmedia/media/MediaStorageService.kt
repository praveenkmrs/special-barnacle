package com.example.socialmedia.media

import java.io.InputStream

interface MediaStorageService {
    fun upload(filename: String, inputStream: InputStream): String
    fun generateSignedUrl(key: String, expirationHours: Int): String
}