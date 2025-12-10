package com.example.marketplace.dto

data class UserActivity(
    val userId: Long,
    val userName: String,
    val action: String,
    val timestamp: String
)