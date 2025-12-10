package com.example.socialmedia.feed

import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/feed")
class FeedController(
    private val feedService: FeedService
) {

    @GetMapping
    fun getUserFeed(
        @RequestParam userId: String,
        @RequestParam(required = false) cursor: String?
    ): ResponseEntity<FeedResponse> {
        val feed = feedService.getUserFeed(userId, cursor)
        return ResponseEntity.ok(feed)
    }
}