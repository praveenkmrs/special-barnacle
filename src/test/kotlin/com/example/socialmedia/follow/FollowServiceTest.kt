package com.example.socialmedia.follow

import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.mock.mockito.MockBean

@SpringBootTest
class FollowServiceTest {

    @MockBean
    private lateinit var followRepository: FollowRepository

    @MockBean
    private lateinit var cacheService: CacheService

    @MockBean
    private lateinit var messagePublisher: MessagePublisher

    @Test
    fun `followUser should create follow relationship and publish to message queue`() {
        val service = FollowService(followRepository, cacheService, messagePublisher)
        val request = FollowRequest(
            followerId = "user123",
            followeeId = "user456"
        )

        // Mock repository behavior
        `when`(followRepository.existsById(any())).thenReturn(false)
        `when`(followRepository.save(any())).thenAnswer { invocation ->
            invocation.getArgument(0) as Follow
        }

        // Call method under test
        val result = service.followUser(request)

        // Verify interactions
        verify(followRepository).existsById(any())
        verify(followRepository).save(any())
        verify(messagePublisher).publishFollowCreated(any())
    }

    @Test
    fun `unfollowUser should remove follow relationship and publish to message queue`() {
        val service = FollowService(followRepository, cacheService, messagePublisher)
        val followId = FollowId("user123", "user456")

        // Mock repository behavior
        `when`(followRepository.existsById(followId)).thenReturn(true)
        doNothing().`when`(followRepository).deleteById(followId)

        // Call method under test
        service.unfollowUser("user123", "user456")

        // Verify interactions
        verify(followRepository).existsById(followId)
        verify(followRepository).deleteById(followId)
        verify(messagePublisher).publishFollowRemoved(followId)
    }
}