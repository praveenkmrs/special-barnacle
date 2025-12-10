package com.example.socialmedia.config

import org.springframework.context.annotation.Configuration

@Configuration
class ShardingConfig {
    // Configuration for sharding strategy
    // Implementation would depend on chosen sharding library
    
    companion object {
        const val NUMBER_OF_SHARDS = 16
    }
}