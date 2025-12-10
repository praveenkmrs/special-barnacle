package com.example.socialmedia.message

import com.example.socialmedia.tweet.Tweet
import com.example.socialmedia.follow.Follow
import com.example.socialmedia.follow.FollowId

interface MessagePublisher {
    fun publishTweetCreated(tweet: Tweet)
    fun publishFollowCreated(follow: Follow)
    fun publishFollowRemoved(followId: FollowId)
}