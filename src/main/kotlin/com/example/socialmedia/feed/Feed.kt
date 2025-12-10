package com.example.socialmedia.feed

data class FeedResponse(
    val tweets: List<TweetResponse>,
    val nextCursor: String?
)

data class TweetResponse(
    val id: String,
    val userId: String,
    val text: String,
    val mediaRefs: List<String>,
    val createdAt: Long
)