package com.example.socialmedia.follow

import org.springframework.stereotype.Service

@Service
class FollowService(
    private val followRepository: FollowRepository,
    private val cacheService: CacheService,
    private val messagePublisher: MessagePublisher
) {

    fun followUser(request: FollowRequest): FollowResponse {
        // Prevent duplicate follows
        if (followRepository.existsById(FollowId(request.followerId, request.followeeId))) {
            throw DuplicateFollowException("Already following user ${request.followeeId}")
        }

        // Create follow relationship
        val follow = Follow(
            followerId = request.followerId,
            followeeId = request.followeeId,
            followedAt = System.currentTimeMillis()
        )

        followRepository.save(follow)

        // Update follower counts
        // This would typically be done with atomic operations in the database
        // For now, we'll assume these are handled by database triggers or application logic

        // Publish to message queue for feed update
        messagePublisher.publishFollowCreated(follow)

        return FollowResponse(
            followerId = follow.followerId,
            followeeId = follow.followeeId,
            followedAt = follow.followedAt
        )
    }

    fun unfollowUser(followerId: String, followeeId: String) {
        val followId = FollowId(followerId, followeeId)
        
        // Only existing follows can be removed
        if (!followRepository.existsById(followId)) {
            throw FollowNotFoundException("Follow relationship not found between $followerId and $followeeId")
        }

        followRepository.deleteById(followId)

        // Decrement counts
        // Similar to followUser, this would be handled by database logic

        // Publish to message queue for feed cleanup
        messagePublisher.publishFollowRemoved(followId)
    }
}