package com.example.socialmedia.media

import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.mock.mockito.MockBean
import org.springframework.web.multipart.MultipartFile

@SpringBootTest
class MediaServiceTest {

    @MockBean
    private lateinit var mediaStorageService: MediaStorageService

    @Test
    fun `uploadMedia should upload to storage and generate signed URL`() {
        val service = MediaService(mediaStorageService)
        val mockFile = mock(MultipartFile::class.java)

        // Mock file behavior
        `when`(mockFile.size).thenReturn(1024L)
        `when`(mockFile.originalFilename).thenReturn("test.jpg")
        `when`(mockFile.inputStream).thenReturn(java.io.ByteArrayInputStream(byteArrayOf()))

        // Mock storage service behavior
        `when`(mediaStorageService.upload("test.jpg", any())).thenReturn("media-key-123")
        `when`(mediaStorageService.generateSignedUrl("media-key-123", 24)).thenReturn("https://example.com/media-key-123")

        // Call method under test
        val result = service.uploadMedia(mockFile)

        // Verify interactions
        verify(mediaStorageService).upload("test.jpg", any())
        verify(mediaStorageService).generateSignedUrl("media-key-123", 24)
    }
}