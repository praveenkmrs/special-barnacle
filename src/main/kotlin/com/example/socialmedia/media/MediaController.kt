package com.example.socialmedia.media

import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.multipart.MultipartFile

@RestController
@RequestMapping("/media")
class MediaController(
    private val mediaService: MediaService
) {

    @PostMapping("/upload")
    fun uploadMedia(@RequestParam("file") file: MultipartFile): ResponseEntity<MediaResponse> {
        val media = mediaService.uploadMedia(file)
        return ResponseEntity.ok(media)
    }
}