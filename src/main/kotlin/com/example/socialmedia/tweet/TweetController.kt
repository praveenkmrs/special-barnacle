package com.example.socialmedia.tweet

import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/tweets")
class TweetController(
    private val tweetService: TweetService
) {

    @PostMapping
    fun createTweet(@RequestBody request: CreateTweetRequest): ResponseEntity<TweetResponse> {
        val tweet = tweetService.createTweet(request)
        return ResponseEntity.ok(tweet)
    }

    @PutMapping("/{id}")
    fun updateTweet(
        @PathVariable id: String,
        @RequestBody request: UpdateTweetRequest
    ): ResponseEntity<TweetResponse> {
        val tweet = tweetService.updateTweet(id, request)
        return ResponseEntity.ok(tweet)
    }

    @DeleteMapping("/{id}")
    fun deleteTweet(@PathVariable id: String): ResponseEntity<Unit> {
        tweetService.deleteTweet(id)
        return ResponseEntity.noContent().build()
    }
}