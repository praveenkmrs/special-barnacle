package com.example.socialmedia.feed

import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository

@Repository
interface FeedRepository : JpaRepository<Follow, FollowId> {
    
    @Query("SELECT f.followeeId FROM Follow f WHERE f.followerId = :userId")
    fun getFollowedUsers(@Param("userId") userId: String): List<String>
}