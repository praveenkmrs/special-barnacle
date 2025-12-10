package com.example.socialmedia.tweet

class TweetNotFoundException(message: String) : RuntimeException(message)
class UnauthorizedAccessException(message: String) : RuntimeException(message)