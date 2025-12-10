package com.example.socialmedia.follow

import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository

@Repository
interface FollowRepository : JpaRepository<Follow, FollowId> {
    fun existsByFollowerIdAndFolloweeId(followerId: String, followeeId: String): Boolean
}