package com.example.socialmedia.follow

class DuplicateFollowException(message: String) : RuntimeException(message)
class FollowNotFoundException(message: String) : RuntimeException(message)