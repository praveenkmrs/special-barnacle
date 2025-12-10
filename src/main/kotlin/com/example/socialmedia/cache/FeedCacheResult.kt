package com.example.socialmedia.cache

data class FeedCacheResult(
    val tweets: List<TweetResponse>,
    val nextCursor: String?
)