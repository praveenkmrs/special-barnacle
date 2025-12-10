package com.example.marketplace.repository

import com.example.marketplace.model.User
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository

@Repository
interface UserRepository : JpaRepository<User, Long> {
    fun findByEmail(email: String): User?
    fun findByGoogleId(googleId: String): User?
    fun findByGithubId(githubId: String): User?
}