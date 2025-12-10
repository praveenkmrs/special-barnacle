package com.example.socialmedia.tweet

import org.springframework.stereotype.Service
import java.util.*

@Service
class TweetService(
    private val tweetRepository: TweetRepository,
    private val cacheService: CacheService,
    private val messagePublisher: MessagePublisher
) {

    fun createTweet(request: CreateTweetRequest): TweetResponse {
        // Validate input
        validateTweetRequest(request)

        // Generate unique tweet ID
        val tweetId = UUID.randomUUID().toString()

        // Create tweet entity
        val tweet = Tweet(
            id = tweetId,
            userId = request.userId,
            text = request.text,
            mediaRefs = request.mediaRefs ?: emptyList(),
            createdAt = System.currentTimeMillis(),
            isDeleted = false
        )

        // Save to database
        tweetRepository.save(tweet)

        // Invalidate cache
        cacheService.invalidateUserFeed(tweet.userId)

        // Publish to message queue for feed updates
        messagePublisher.publishTweetCreated(tweet)

        return TweetResponse(
            id = tweet.id,
            userId = tweet.userId,
            text = tweet.text,
            mediaRefs = tweet.mediaRefs,
            createdAt = tweet.createdAt
        )
    }

    fun updateTweet(tweetId: String, request: UpdateTweetRequest): TweetResponse {
        val tweet = tweetRepository.findById(tweetId)
            .orElseThrow { TweetNotFoundException("Tweet not found: $tweetId") }

        // Check ownership
        if (tweet.userId != request.userId) {
            throw UnauthorizedAccessException("Not authorized to edit this tweet")
        }

        // Update tweet
        val updatedTweet = tweet.copy(
            text = request.text,
            mediaRefs = request.mediaRefs ?: tweet.mediaRefs
        )

        tweetRepository.save(updatedTweet)

        // Invalidate cache
        cacheService.invalidateTweetCache(tweetId)

        return TweetResponse(
            id = updatedTweet.id,
            userId = updatedTweet.userId,
            text = updatedTweet.text,
            mediaRefs = updatedTweet.mediaRefs,
            createdAt = updatedTweet.createdAt
        )
    }

    fun deleteTweet(tweetId: String) {
        val tweet = tweetRepository.findById(tweetId)
            .orElseThrow { TweetNotFoundException("Tweet not found: $tweetId") }

        // Check ownership
        if (tweet.userId != tweet.userId) {
            throw UnauthorizedAccessException("Not authorized to delete this tweet")
        }

        // Soft delete
        val deletedTweet = tweet.copy(isDeleted = true)
        tweetRepository.save(deletedTweet)

        // Remove from cache
        cacheService.removeTweetFromFeed(tweetId)

        // Schedule media cleanup (placeholder for actual implementation)
        scheduleMediaCleanup(tweet.mediaRefs)
    }

    private fun validateTweetRequest(request: CreateTweetRequest) {
        if (request.text.length > MAX_TWEET_LENGTH) {
            throw IllegalArgumentException("Tweet text exceeds maximum length of $MAX_TWEET_LENGTH characters")
        }
        // Validate media size limits (placeholder for actual implementation)
    }

    private fun scheduleMediaCleanup(mediaRefs: List<String>) {
        // Placeholder for media cleanup job scheduling
        // Implementation would involve calling a media cleanup service
    }

    companion object {
        const val MAX_TWEET_LENGTH = 140
    }
}