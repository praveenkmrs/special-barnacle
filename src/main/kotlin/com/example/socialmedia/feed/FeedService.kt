package com.example.socialmedia.feed

import org.springframework.stereotype.Service

@Service
class FeedService(
    private val feedRepository: FeedRepository,
    private val tweetRepository: TweetRepository,
    private val cacheService: CacheService
) {

    fun getUserFeed(userId: String, cursor: String?): FeedResponse {
        // Try to get from cache first (cache hit)
        val cachedFeed = cacheService.getFeed(userId, cursor)
        if (cachedFeed != null) {
            return cachedFeed
        }

        // Cache miss - fallback to database query
        val feed = fetchFeedFromDatabase(userId, cursor)
        
        // Cache the result
        cacheService.setFeed(userId, feed, cursor)
        
        return feed
    }

    private fun fetchFeedFromDatabase(userId: String, cursor: String?): FeedResponse {
        // Get followed users
        val followedUsers = feedRepository.getFollowedUsers(userId)
        
        // Fetch tweets from followed users
        val tweets = tweetRepository.findByUserIdsAndNotDeleted(followedUsers)
            .sortedByDescending { it.createdAt }
            .take(20)
        
        // Create response with pagination cursor
        val nextCursor = if (tweets.size == 20) generateNextCursor(tweets.last()) else null
        
        return FeedResponse(
            tweets = tweets.map { tweet ->
                TweetResponse(
                    id = tweet.id,
                    userId = tweet.userId,
                    text = tweet.text,
                    mediaRefs = tweet.mediaRefs,
                    createdAt = tweet.createdAt
                )
            },
            nextCursor = nextCursor
        )
    }

    private fun generateNextCursor(lastTweet: Tweet): String {
        // Generate cursor based on timestamp and tweet ID
        return "${lastTweet.createdAt}_${lastTweet.id}"
    }
}