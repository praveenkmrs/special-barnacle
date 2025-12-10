package com.example.socialmedia.media

import org.springframework.stereotype.Service
import java.io.InputStream

@Service
class MediaService(
    private val mediaStorageService: MediaStorageService
) {

    fun uploadMedia(file: MultipartFile): MediaResponse {
        // Validate file size (placeholder for actual validation)
        if (file.size > MAX_MEDIA_SIZE) {
            throw IllegalArgumentException("File size exceeds maximum allowed size")
        }

        // Upload to object storage
        val mediaKey = mediaStorageService.upload(file.originalFilename!!, file.inputStream)
        
        // Generate signed URL with expiration
        val signedUrl = mediaStorageService.generateSignedUrl(mediaKey, EXPIRATION_HOURS)
        
        return MediaResponse(
            url = signedUrl,
            key = mediaKey
        )
    }

    companion object {
        const val MAX_MEDIA_SIZE = 10 * 1024 * 1024 // 10MB
        const val EXPIRATION_HOURS = 24
    }
}