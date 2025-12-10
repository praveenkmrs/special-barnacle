package com.example.socialmedia.tweet

import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.mock.mockito.MockBean

@SpringBootTest
class TweetServiceTest {

    @MockBean
    private lateinit var tweetRepository: TweetRepository

    @MockBean
    private lateinit var cacheService: CacheService

    @MockBean
    private lateinit var messagePublisher: MessagePublisher

    @Test
    fun `createTweet should save tweet and publish to message queue`() {
        val service = TweetService(tweetRepository, cacheService, messagePublisher)
        val request = CreateTweetRequest(
            userId = "user123",
            text = "Hello world!",
            mediaRefs = listOf("media1", "media2")
        )

        // Mock repository behavior
        `when`(tweetRepository.save(any())).thenAnswer { invocation ->
            invocation.getArgument(0) as Tweet
        }

        // Call method under test
        val result = service.createTweet(request)

        // Verify interactions
        verify(tweetRepository).save(any())
        verify(cacheService).invalidateUserFeed("user123")
        verify(messagePublisher).publishTweetCreated(any())
    }

    @Test
    fun `updateTweet should update tweet and invalidate cache`() {
        val service = TweetService(tweetRepository, cacheService, messagePublisher)
        val tweet = Tweet(
            id = "tweet123",
            userId = "user123",
            text = "Original text",
            mediaRefs = emptyList(),
            createdAt = 1234567890,
            isDeleted = false
        )
        val request = UpdateTweetRequest(
            userId = "user123",
            text = "Updated text",
            mediaRefs = listOf("media1")
        )

        // Mock repository behavior
        `when`(tweetRepository.findById("tweet123")).thenReturn(java.util.Optional.of(tweet))
        `when`(tweetRepository.save(any())).thenAnswer { invocation ->
            invocation.getArgument(0) as Tweet
        }

        // Call method under test
        val result = service.updateTweet("tweet123", request)

        // Verify interactions
        verify(tweetRepository).findById("tweet123")
        verify(tweetRepository).save(any())
        verify(cacheService).invalidateTweetCache("tweet123")
    }

    @Test
    fun `deleteTweet should soft delete and remove from cache`() {
        val service = TweetService(tweetRepository, cacheService, messagePublisher)
        val tweet = Tweet(
            id = "tweet123",
            userId = "user123",
            text = "Hello world!",
            mediaRefs = emptyList(),
            createdAt = 1234567890,
            isDeleted = false
        )

        // Mock repository behavior
        `when`(tweetRepository.findById("tweet123")).thenReturn(java.util.Optional.of(tweet))
        `when`(tweetRepository.save(any())).thenAnswer { invocation ->
            invocation.getArgument(0) as Tweet
        }

        // Call method under test
        service.deleteTweet("tweet123")

        // Verify interactions
        verify(tweetRepository).findById("tweet123")
        verify(tweetRepository).save(any())
        verify(cacheService).removeTweetFromFeed("tweet123")
    }
}