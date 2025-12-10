package com.example.socialmedia.follow

data class Follow(
    val followerId: String,
    val followeeId: String,
    val followedAt: Long
)

data class FollowRequest(
    val followerId: String,
    val followeeId: String
)

data class FollowResponse(
    val followerId: String,
    val followeeId: String,
    val followedAt: Long
)

data class FollowId(
    val followerId: String,
    val followeeId: String
)