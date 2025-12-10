package com.example.socialmedia.tweet

import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository

@Repository
interface TweetRepository : JpaRepository<Tweet, String> {
    
    @Query("SELECT t FROM Tweet t WHERE t.userId = :userId AND t.isDeleted = false ORDER BY t.createdAt DESC")
    fun findByUserIdOrderByCreatedAtDesc(@Param("userId") userId: String): List<Tweet>
    
    @Query("SELECT t FROM Tweet t WHERE t.id = :id AND t.isDeleted = false")
    fun findByIdAndNotDeleted(@Param("id") id: String): Optional<Tweet>
    
    @Query("SELECT t FROM Tweet t WHERE t.userId IN :userIds AND t.isDeleted = false ORDER BY t.createdAt DESC")
    fun findByUserIdsAndNotDeleted(@Param("userIds") userIds: List<String>): List<Tweet>
}