package com.example.socialmedia.tweet

import java.util.*

data class Tweet(
    val id: String,
    val userId: String,
    val text: String,
    val mediaRefs: List<String>,
    val createdAt: Long,
    val isDeleted: Boolean
)

data class CreateTweetRequest(
    val userId: String,
    val text: String,
    val mediaRefs: List<String>?
)

data class UpdateTweetRequest(
    val userId: String,
    val text: String,
    val mediaRefs: List<String>?
)

data class TweetResponse(
    val id: String,
    val userId: String,
    val text: String,
    val mediaRefs: List<String>,
    val createdAt: Long
)