package com.example.marketplace.dto

data class AuthResponse(
    val token: String,
    val user: UserDto
)