package com.example.socialmedia.feed

import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.mock.mockito.MockBean

@SpringBootTest
class FeedServiceTest {

    @MockBean
    private lateinit var feedRepository: FeedRepository

    @MockBean
    private lateinit var tweetRepository: TweetRepository

    @MockBean
    private lateinit var cacheService: CacheService

    @Test
    fun `getUserFeed should return cached feed when available`() {
        val service = FeedService(feedRepository, tweetRepository, cacheService)
        
        // Mock cache behavior
        `when`(cacheService.getFeed("user123", null)).thenReturn(
            FeedResponse(
                tweets = emptyList(),
                nextCursor = null
            )
        )

        // Call method under test
        val result = service.getUserFeed("user123", null)

        // Verify interactions
        verify(cacheService).getFeed("user123", null)
        verifyNoInteractions(feedRepository)
        verifyNoInteractions(tweetRepository)
    }

    @Test
    fun `getUserFeed should fetch from database when cache miss`() {
        val service = FeedService(feedRepository, tweetRepository, cacheService)
        
        // Mock cache behavior to simulate cache miss
        `when`(cacheService.getFeed("user123", null)).thenReturn(null)
        
        // Mock repository behavior
        `when`(feedRepository.getFollowedUsers("user123")).thenReturn(listOf("user456"))
        `when`(tweetRepository.findByUserIdsAndNotDeleted(listOf("user456"))).thenReturn(emptyList())

        // Call method under test
        val result = service.getUserFeed("user123", null)

        // Verify interactions
        verify(cacheService).getFeed("user123", null)
        verify(feedRepository).getFollowedUsers("user123")
        verify(tweetRepository).findByUserIdsAndNotDeleted(listOf("user456"))
        verify(cacheService).setFeed("user123", any(), any())
    }
}